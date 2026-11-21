"""Run fixed-profile Xiaoyu voice generation for saved manuscript versions."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rewrite_system

VOICE_ROOT = Path(r"E:\wwai\qwen3-tts\outputs\xiaoyu").resolve()
TTS_PYTHON = Path(r"E:\wwai\qwen3-tts\.venv\Scripts\python.exe")
WORKER = Path(__file__).with_name("rewrite_voice_worker.py")
FILE_PATTERN = re.compile(r"^rewrite_([0-9a-f-]{36})_(v\d+)_([0-9a-f]{12})\.wav$")
JOBS: dict[str, dict] = {}
LATEST: dict[tuple[str, str], str] = {}
JOB_LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xiaoyu-rewrite")


def audio_path(filename: str) -> Path:
    if not FILE_PATTERN.fullmatch(filename):
        raise rewrite_system.RewriteError("语音文件名无效")
    path = (VOICE_ROOT / filename).resolve()
    if not path.is_relative_to(VOICE_ROOT):
        raise rewrite_system.RewriteError("语音文件路径无效")
    return path


def spoken_text(script: str) -> str:
    return "\n".join(re.sub(r"^\[\d{2}:\d{2}\]\s*", "", line).strip()
                     for line in script.splitlines() if line.strip()).strip()


def get_version(manuscript_id: str, version_id: str):
    data = rewrite_system.dispatch({"action": "list"})
    manuscript = rewrite_system.find(data["manuscripts"], manuscript_id, "稿件")
    version = rewrite_system.find(manuscript["transcriptVersions"], version_id, "逐字稿版本")
    return manuscript, version


def start(manuscript_id: str, version_id: str) -> dict:
    if not TTS_PYTHON.is_file() or not WORKER.is_file():
        raise rewrite_system.RewriteError("本地小与语音环境不完整")
    manuscript, version = get_version(manuscript_id, version_id)
    if manuscript["activeTranscriptVersionId"] != version_id:
        raise rewrite_system.RewriteError("请先切换到要生成语音的版本")
    text = spoken_text(version["text"])
    if not text:
        raise rewrite_system.RewriteError("当前版本没有可朗读的口播内容")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    filename = f"rewrite_{manuscript_id}_{version_id}_{digest}.wav"
    target = audio_path(filename)
    url = f"/assets/rewrite-audio/{filename}"
    if target.is_file() and target.stat().st_size > 44:
        metadata = {"url": url, "sourceTextHash": digest, "generatedAt": rewrite_system.now(),
                    "profile": "小与", "bytes": target.stat().st_size}
        rewrite_system.attach_voice_audio(manuscript_id, version_id, metadata)
        return {"state": "done", "audio": metadata, "versionId": version_id}
    key = (manuscript_id, version_id)
    with JOB_LOCK:
        old_id = LATEST.get(key)
        old_job = JOBS.get(old_id) if old_id else None
        if old_job and old_job["state"] in ("queued", "running") and old_job["sourceTextHash"] == digest:
            return dict(old_job)
        job_id = uuid.uuid4().hex
        job = {"jobId": job_id, "manuscriptId": manuscript_id, "versionId": version_id,
               "sourceTextHash": digest, "state": "queued", "audio": None, "error": ""}
        JOBS[job_id] = job
        LATEST[key] = job_id
        POOL.submit(_run, job_id, text, target, url)
        return dict(job)


def status(job_id: str = "", manuscript_id: str = "", version_id: str = "") -> dict:
    with JOB_LOCK:
        if not job_id:
            job_id = LATEST.get((manuscript_id, version_id), "")
        job = JOBS.get(job_id)
        result = dict(job) if job else {"state": "idle", "jobId": "", "audio": None, "error": ""}
    if job and manuscript_id and version_id:
        _, version = get_version(manuscript_id, version_id)
        digest = hashlib.sha256(spoken_text(version['text']).encode('utf-8')).hexdigest()[:12]
        if digest != result['sourceTextHash']:
            return {"state": "stale", "jobId": job_id, "audio": None, "error": "稿件已修改，请重新生成语音"}
    return result


def _run(job_id: str, text: str, target: Path, url: str) -> None:
    with JOB_LOCK:
        JOBS[job_id]["state"] = "running"
        job = dict(JOBS[job_id])
    VOICE_ROOT.mkdir(parents=True, exist_ok=True)
    text_file = target.with_suffix(".txt")
    try:
        text_file.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [str(TTS_PYTHON), "-X", "utf8", str(WORKER), "--text-file", str(text_file), "--output", str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "生成失败")[-800:])
        if not target.is_file() or target.stat().st_size <= 44:
            raise RuntimeError("语音文件未生成")
        with target.open("rb") as handle:
            header = handle.read(12)
        if header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise RuntimeError("生成文件不是有效 WAV")
        metadata = {"url": url, "sourceTextHash": job["sourceTextHash"],
                    "generatedAt": rewrite_system.now(), "profile": "小与",
                    "bytes": target.stat().st_size}
        rewrite_system.attach_voice_audio(job["manuscriptId"], job["versionId"], metadata)
        with JOB_LOCK:
            JOBS[job_id].update({"state": "done", "audio": metadata})
    except Exception as exc:
        with JOB_LOCK:
            JOBS[job_id].update({"state": "error", "error": str(exc)[-800:]})
    finally:
        try:
            text_file.unlink(missing_ok=True)
        except OSError:
            pass
