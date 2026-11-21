"""Serial retries, durable six-stage backoff and visible wait status."""
from __future__ import annotations

import asyncio
import json
import math
import random
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

TIERS = ((1, 5), (5, 20), (20, 60), (60, 180), (180, 600), (600, 3600))
RESTRICTIONS = {"access_denied", "login_required", "challenge_required", "manual_window_closed"}
TERMINAL = {"identity_mismatch", "private_account", "invalid_target"}


def now():
    return datetime.now(timezone.utc)


def atomic_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def retry_after_seconds(response):
    """Read Retry-After without persisting response headers."""
    value = response.headers.get("retry-after", "")
    try:
        delay = float(value)
        return max(0, delay) if math.isfinite(delay) else 0
    except (ValueError, TypeError):
        try:
            return max(0, (parsedate_to_datetime(value) - now()).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0


class Pacer:
    def __init__(self, args):
        self.interval = getattr(args, "account_delay", 8)
        self.streak = 0
        self.events = []
        self.stop_reason = None
        self.slow_factor = 1
        self.healthy_streak = 0
        self.pending_unit = None
        self.wake_at = None
        self.status = "running"
        self.state = {}
        self.save = lambda: None

    def snapshot(self):
        return {"events": self.events, "stop_reason": self.stop_reason, "streak": self.streak,
                "slow_factor": self.slow_factor, "healthy_streak": self.healthy_streak,
                "pending_unit": self.pending_unit, "wake_at": self.wake_at, "status": self.status}

    def persist(self):
        self.state["pacing"] = self.snapshot()
        self.save()

    def bind(self, state, save):
        self.state, self.save = state, save
        previous = state.get("pacing", {})
        self.events = list(previous.get("events", []))
        self.streak = previous.get("streak", 0)
        self.slow_factor = previous.get("slow_factor", 1)
        self.healthy_streak = previous.get("healthy_streak", 0)
        self.pending_unit = previous.get("pending_unit")
        self.wake_at = previous.get("wake_at")
        self.status = previous.get("status", "running")
        self.stop_reason = None

    def observe(self, *, error=None, usable=True, exhausted=False, retry_after=0):
        abnormal = bool(error) or (not usable and not exhausted)
        if error in RESTRICTIONS:
            self.stop_reason = error
            self.status = "needs_attention"
            delay = 0
        elif error in TERMINAL:
            delay = self.interval * self.slow_factor
        elif abnormal:
            self.streak += 1
            self.healthy_streak = 0
            self.slow_factor = min(8, self.slow_factor * 2)
            stage = 6 if error == "rate_limited" else min(self.streak, 6)
            low, high = TIERS[stage - 1]
            delay = max(random.uniform(low, high), retry_after)
        else:
            self.streak = 0
            self.healthy_streak += 1
            if self.healthy_streak >= 3:
                self.slow_factor = max(1, self.slow_factor // 2)
                self.healthy_streak = 0
            delay = self.interval * self.slow_factor
        if abnormal:
            event = {"reason": error or "no_usable_data", "unit": self.pending_unit,
                     "consecutive_anomalies": self.streak,
                     "stage": (6 if error == "rate_limited" else min(self.streak, 6)) if error not in RESTRICTIONS | TERMINAL else None,
                     "cooldown_seconds": delay, "retry_after": (now() + timedelta(seconds=delay)).isoformat(),
                     "stopped": bool(self.stop_reason), "slow_factor": self.slow_factor}
            self.events.append(event)
            print(json.dumps({"collection_pacing": event}, ensure_ascii=False), flush=True)
        return delay

    async def pause(self, delay, *, restoring=False):
        if not restoring:
            self.wake_at = (now() + timedelta(seconds=delay)).isoformat()
        self.status = "waiting"
        self.persist()
        remaining = max(0, (datetime.fromisoformat(self.wake_at) - now()).total_seconds())
        elapsed = 0
        while remaining > 0:
            if elapsed == 0 or elapsed >= 30:
                print(json.dumps({"collection_wait": {"status": "waiting", "unit": self.pending_unit,
                      "consecutive_anomalies": self.streak, "remaining_seconds": round(remaining, 1),
                      "reason": self.events[-1]["reason"] if self.streak and self.events else "task_interval",
                      "unique_videos": len(self.state.get("pool", {})), "completed_units": len(self.state.get("results", {})),
                      "resume_at": self.wake_at, "message": "任务仍在运行：等待结束后继续采集；Ctrl+C 可保存进度退出。"}}, ensure_ascii=False), flush=True)
                self.persist()
                elapsed = 0
            step = min(10, remaining)
            await asyncio.sleep(step)
            remaining = max(0, remaining - step)
            elapsed += step
        self.wake_at = None
        self.status = "running"
        self.persist()
        print(json.dumps({"collection_wait": {"status": "resuming", "unit": self.pending_unit}}, ensure_ascii=False), flush=True)

    async def resume_wait(self):
        if self.wake_at:
            await self.pause(0, restoring=True)

    async def run(self, operation, unit, assess):
        """Retry the same unit until usable/exhausted, terminal, or genuine access block."""
        self.pending_unit = unit
        self.status = "running"
        self.persist()
        while True:
            result = await operation()
            assessment = assess(result)
            error = assessment.get("error")
            healthy = not error and (assessment.get("usable", True) or assessment.get("exhausted", False))
            delay = self.observe(**assessment)
            self.persist()
            if healthy or error in TERMINAL or self.stop_reason:
                if not self.stop_reason:
                    self.pending_unit = None
                self.persist()
                return result
            await self.pause(delay)


def bind_checkpoint(args, signature):
    """Account/video checkpoint containing only public results and scheduling state."""
    state = {"signature": signature, "results": {}}
    if args.resume and args.checkpoint.is_file():
        state = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if state.get("signature") != signature:
            raise ValueError("Checkpoint targets/options differ; choose a separate --checkpoint.")
    pacer = pacer_for(args)
    pacer.bind(state, lambda: atomic_state(args.checkpoint, state))
    pacer.persist()
    return pacer, state


def pacer_for(args):
    if not hasattr(args, "_pacer"):
        args._pacer = Pacer(args)
    return args._pacer


async def scroll_pause(page, args):
    await page.wait_for_timeout(args.wait_ms * pacer_for(args).slow_factor)
