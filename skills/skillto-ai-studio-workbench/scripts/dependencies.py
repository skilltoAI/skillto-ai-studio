"""Resolve real FFmpeg; never bundle an executable in the distributable skill."""
import os
from pathlib import Path
import shutil

def ffmpeg_path():
    explicit = os.environ.get('SKILLTO_FFMPEG_LOCATION')
    if explicit:
        path = Path(explicit)
        if path.is_dir(): path = path / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        return str(path) if path.is_file() else None
    system = shutil.which('ffmpeg')
    if system: return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None
