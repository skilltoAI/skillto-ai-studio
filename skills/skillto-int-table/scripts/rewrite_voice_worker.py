"""Generate one version's WAV with the fixed Xiaoyu profile, in manageable chunks."""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import socket
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

XIAOYU_HELPER = Path(r"C:\Users\Administrator\.codex\skills\xiaoyu-voice\scripts\generate_xiaoyu.py")
spec = importlib.util.spec_from_file_location("fixed_xiaoyu_helper", XIAOYU_HELPER)
if spec is None or spec.loader is None:
    raise RuntimeError("小与语音 skill 未安装")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def spoken_chunks(raw: str, limit: int = 180) -> list[str]:
    lines = [re.sub(r"^\[\d{2}:\d{2}\]\s*", "", line).strip()
             for line in raw.splitlines()]
    source = "\n".join(line for line in lines if line)
    pieces = [piece.strip() for piece in re.split(r"(?<=[。！？!?；;])", source) if piece.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        while len(piece) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(piece[:limit])
            piece = piece[limit:]
        if not piece:
            continue
        if current and len(current) + len(piece) > limit:
            chunks.append(current)
            current = ""
        current += piece
    if current:
        chunks.append(current)
    return chunks


def webui_client():
    try:
        with socket.create_connection(("127.0.0.1", 8002), timeout=2):
            pass
        from gradio_client import Client
        return Client(helper.WEBUI_URL, verbose=False)
    except Exception:
        return None


def generated_audio(chunks: list[str]):
    client = webui_client()
    if client is not None:
        try:
            for chunk in chunks:
                path = Path(client.predict(chunk, api_name="/synthesize"))
                yield sf.read(path, dtype="float32")
            return
        except Exception as exc:
            raise RuntimeError(f"小与 WebUI 生成失败：{exc}") from exc

    import torch
    from qwen_tts import Qwen3TTSModel

    model = Qwen3TTSModel.from_pretrained(
        str(helper.MODEL_DIR), device_map="cuda:0", dtype=torch.bfloat16
    )
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(helper.PROFILE_DIR / "reference.wav"),
        ref_text=(helper.PROFILE_DIR / "reference.txt").read_text(encoding="utf-8"),
        x_vector_only_mode=False,
    )
    for chunk in chunks:
        wavs, rate = model.generate_voice_clone(
            text=chunk, language="Chinese", voice_clone_prompt=prompt,
            non_streaming_mode=True,
        )
        yield np.asarray(wavs[0], dtype=np.float32), rate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (helper.PROFILE_DIR / "reference.wav").is_file() or not (helper.PROFILE_DIR / "reference.txt").is_file():
        raise FileNotFoundError("固定小与音色资源不完整")
    chunks = spoken_chunks(args.text_file.read_text(encoding="utf-8"))
    if not chunks:
        raise ValueError("当前版本没有可朗读的正文")
    print(f"小与语音：{len(chunks)} 段", flush=True)
    audio_parts = []
    sample_rate = None
    for index, (audio, rate) in enumerate(generated_audio(chunks), 1):
        if sample_rate is None:
            sample_rate = rate
        elif rate != sample_rate:
            raise RuntimeError("分段采样率不一致")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio_parts.append(audio)
        if index < len(chunks):
            audio_parts.append(np.zeros(int(sample_rate * 0.12), dtype=np.float32))
        print(f"已生成 {index}/{len(chunks)} 段", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.stem + ".partial.wav")
    sf.write(temporary, np.concatenate(audio_parts), sample_rate)
    os.replace(temporary, args.output)
    print(args.output.resolve(), flush=True)


if __name__ == "__main__":
    main()
