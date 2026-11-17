"""Sample exact timestamps and rank frame-to-frame hard-cut candidates."""

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def probe(ffprobe: Path, source: Path) -> tuple[float, float, dict]:
    raw = subprocess.check_output([str(ffprobe), "-v", "error", "-show_entries",
                                   "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(source)])
    data = json.loads(raw)
    video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
    return float(data["format"]["duration"]), float(Fraction(video["r_frame_rate"])), data


def sample(ffmpeg: Path, source: Path, duration: float, step: float, directory: Path) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    output = []
    count = int(duration / step + 1e-8)
    for index in range(count):
        t = min(duration - 0.01, (index + 0.5) * step)
        path = directory / f"frame-{t:06.2f}s.jpg"
        subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.4f}",
                        "-i", str(source), "-frames:v", "1", "-q:v", "2", "-y", str(path)], check=True)
        if not path.is_file():
            raise RuntimeError(f"Frame extraction failed at {t:.2f}s")
        output.append({"time_s": round(t, 4), "file": path.name})
    return output


def cut_scores(ffmpeg: Path, source: Path, fps: float, directory: Path) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    pattern = str(directory / "frame-%05d.jpg")
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-vf", "scale=64:64", "-q:v", "5", "-y", pattern]
    subprocess.run(command, capture_output=True, check=True)
    files = sorted(directory.glob("frame-*.jpg"))
    scores = []
    previous = None
    for index, file in enumerate(files):
        with Image.open(file) as image:
            frame = image.convert("RGB")
        if previous is not None:
            diff = ImageChops.difference(previous, frame)
            score = sum(ImageStat.Stat(diff).mean) / 3
            scores.append({"frame": index, "time_s": round(index / fps, 4), "mean_rgb_delta": round(score, 3)})
        previous = frame
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--step", type=float, default=0.5)
    args = parser.parse_args()
    if args.step <= 0:
        raise ValueError("step must be positive")
    source = args.source.resolve(strict=True)
    duration, fps, probe_data = probe(args.ffprobe, source)
    frames = sample(args.ffmpeg, source, duration, args.step, args.output_dir / "frames")
    scores = cut_scores(args.ffmpeg, source, fps, args.output_dir / "cut-thumbs")
    result = {"source": str(source), "duration_s": duration, "fps": fps,
              "streams": probe_data["streams"], "sampling_step_s": args.step,
              "sampled_frames": frames, "frame_change_scores": scores}
    destination = args.output_dir / "timeline_manifest.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    top = sorted(scores, key=lambda item: item["mean_rgb_delta"], reverse=True)[:8]
    print(json.dumps({"duration_s": duration, "fps": fps, "sampled_frames": len(frames),
                      "decoded_frames": len(scores) + 1, "top_change_candidates": top}, ensure_ascii=False))


if __name__ == "__main__":
    main()
