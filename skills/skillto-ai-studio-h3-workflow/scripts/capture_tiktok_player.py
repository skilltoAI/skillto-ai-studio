"""Save the MP4 response from one crawler-verified, authorized TikTok player."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skillto-ai-studio-tiktok-crawler" / "scripts"))
from auth import load_cookies

from playwright.async_api import async_playwright


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    videos = data.get("videos", [])
    if len(videos) != 1 or videos[0].get("verification") != "video_page_and_author_profile_verified":
        raise ValueError("Expected one crawler-verified TikTok video")
    video = videos[0]
    target = video["item_url"]
    captured = []
    finished = asyncio.Event()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(locale="en-US")
        await context.add_cookies(load_cookies())
        page = await context.new_page()

        async def on_response(response):
            content_type = response.headers.get("content-type", "").lower()
            if response.status not in (200, 206):
                return
            if not (content_type.startswith("video/") or "video_mp4" in response.url):
                return
            try:
                body = await response.body()
            except Exception:
                return
            if len(body) > 100_000 and b"ftyp" in body[:64] and response.status == 200:
                captured.append((len(body), content_type, body))
                finished.set()

        page.on("response", on_response)
        for attempt in range(3):
            await page.goto(target, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(5_000)
            player = page.locator("video")
            if await player.count():
                try:
                    await player.first.evaluate("v => { v.muted = true; v.play().catch(() => {}); }")
                except Exception:
                    pass
            try:
                await asyncio.wait_for(finished.wait(), timeout=24)
            except asyncio.TimeoutError:
                pass
            if captured:
                break
            if attempt < 2:
                await page.wait_for_timeout(3_000)
        await browser.close()
    if not captured:
        print("public-player-media-response=none")
        return
    size, content_type, body = max(captured, key=lambda x: x[0])
    if body[:4] not in (b"\x00\x00\x00\x18", b"\x00\x00\x00\x1c", b"\x00\x00\x00\x20") and b"ftyp" not in body[:64]:
        raise ValueError("Captured response is not an MP4 header")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)
    video.pop("media_url", None)
    video.pop("cover_url", None)
    args.report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"public-player-media-response={content_type} bytes={size}")


if __name__ == "__main__":
    asyncio.run(main())
