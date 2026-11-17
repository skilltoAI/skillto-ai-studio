"""Frame-accurate local range export with the configured FFmpeg."""
import math
import subprocess
from dependencies import ffmpeg_path


def cut_video(source, target, start, end):
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= 86400:
        raise ValueError('片段范围无效')
    binary = ffmpeg_path()
    if not binary: raise ValueError('缺少 FFmpeg')
    subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-ss', str(start), '-i', str(source), '-t', str(end - start),
        '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(target)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
