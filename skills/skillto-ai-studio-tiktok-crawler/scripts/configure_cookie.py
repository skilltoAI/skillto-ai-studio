from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from auth import cookie_path, load_cookies, write_cookie


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure TikTok cookies without echoing values.")
    parser.add_argument("--path", type=Path)
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--check", action="store_true", help="Syntax/expiry check only, not a live login check.")
    args = parser.parse_args()
    path = cookie_path(args.path)
    if args.check:
        cookies = load_cookies(path)
        print(f"Cookie syntax checked ({len(cookies)} fields, values hidden). Live login not verified.")
    else:
        if not args.stdin and not sys.stdin.isatty():
            raise ValueError("Interactive terminal required; use --stdin with a protected input stream.")
        value = sys.stdin.read() if args.stdin else getpass.getpass("TikTok Cookie (hidden): ")
        write_cookie(path, value, replace=args.replace)
        print(f"Cookie saved privately: {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "Cookie setup failed; check file permissions.", file=sys.stderr)
        raise SystemExit(2)
