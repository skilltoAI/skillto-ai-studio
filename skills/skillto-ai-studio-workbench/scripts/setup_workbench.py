"""Check/install explicitly requested runtime dependencies and show human steps."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from dependencies import ffmpeg_path
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-deps', action='store_true', help='Install yt-dlp[default] and imageio-ffmpeg in this Python environment')
    args = parser.parse_args()
    if args.install_deps:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp[default]', 'imageio-ffmpeg'], check=True)
    ffmpeg = ffmpeg_path()
    ok = bool(importlib.util.find_spec('yt_dlp'))
    print(json.dumps({'python': sys.executable, 'ytDlp': ok, 'ffmpeg': bool(ffmpeg),
                      'catExtensionDirectory': os.environ.get('SKILLTO_CAT_EXTENSION_DIR'),
                      'catBuildScript': str(Path(__file__).with_name('build_cat_extension.py').resolve())}, ensure_ascii=False, indent=2))
    print('猫抓修改版：运行 catBuildScript，明确指定官方源码 --source 与稳定输出 --destination；在 Chrome 加载该输出目录，不要加载 overlay 目录。')
    print('固定 Skillto-AI-Studio 到工具栏。普通下载由 Chrome 完成；选段与同步到工作台自动连接本机，不需要配置端口或复制连接码。')
    print('如 Chrome 提示本地网络访问，请允许本插件访问本机工作台。安装和启用不能用普通网页代替。')
    return 0 if ok and ffmpeg else 1

if __name__ == '__main__': sys.exit(main())
