"""TikTok-only cookie loading. Never include cookie contents in exceptions."""
from __future__ import annotations

import csv
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from pathlib import Path


def default_cookie_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "skillto.ai/secrets/tiktok-cookie.txt"
    return Path.home() / ".config/skillto.ai/secrets/tiktok-cookie.txt"


def cookie_path(explicit: str | Path | None = None) -> Path:
    return Path(explicit or os.environ.get("TIKTOK_COOKIE_FILE") or default_cookie_path()).expanduser().resolve()


def is_tiktok_host(host: str) -> bool:
    return host == "tiktok.com" or host.endswith(".tiktok.com")


def parse_cookies(text: str) -> list[dict]:
    text = text.strip().lstrip("\ufeff")
    try:
        if text.startswith(("[", "{")):
            raw = json.loads(text)
            raw = raw.get("cookies") if isinstance(raw, dict) else raw
            if not isinstance(raw, list):
                raise ValueError
        elif "\t" in text:
            raw = []
            for line in text.splitlines():
                if line.startswith("#HttpOnly_"):
                    line = line[len("#HttpOnly_"):]
                elif line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) != 7:
                    raise ValueError
                domain, _, path, secure, expires, name, value = parts
                raw.append(dict(domain=domain, path=path, secure=secure.upper() == "TRUE",
                                expires=float(expires) or -1, name=name, value=value))
        else:
            if text.lower().startswith("cookie:"):
                text = text.split(":", 1)[1].strip()
            if "\n" in text or "\r" in text:
                raise ValueError
            raw = []
            for pair in text.split(";"):
                if not pair.strip():
                    continue
                if "=" not in pair:
                    raise ValueError
                name, value = pair.strip().split("=", 1)
                raw.append(dict(name=name, value=value, domain=".tiktok.com", path="/", secure=True))
        result = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError
            domain = str(item.get("domain") or "")
            if not is_tiktok_host(domain.lstrip(".").lower()):
                continue
            name, value = item.get("name"), item.get("value")
            if not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~\w-]+", name):
                raise ValueError
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError
            expires = float(item.get("expires", item.get("expirationDate", -1)))
            if expires > 0 and expires <= time.time():
                continue
            cookie = dict(name=name, value=value, domain=domain, path=item.get("path") or "/",
                          secure=bool(item.get("secure", True)), httpOnly=bool(item.get("httpOnly", False)))
            if expires > 0:
                cookie["expires"] = expires
            if item.get("sameSite") in {"Strict", "Lax", "None"}:
                cookie["sameSite"] = item["sameSite"]
            result.append(cookie)
        if not any(c["name"] in {"sessionid", "sessionid_ss", "sid_tt"} and c["value"] for c in result):
            raise ValueError
        return result
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("Invalid TikTok cookie format or no unexpired session field; values hidden.") from None


def load_cookies(explicit: str | Path | None = None) -> list[dict]:
    path = cookie_path(explicit)
    if not path.is_file():
        raise ValueError(f"Authenticated TikTok cookie required. Expected file: {path}. "
                         "Run scripts/configure_cookie.py; see references/cookie-setup.md.")
    try:
        return parse_cookies(path.read_text(encoding="utf-8-sig"))
    except OSError:
        raise ValueError("Cannot read TikTok cookie file; check file access.") from None


def write_cookie(path: Path, text: str, *, replace: bool = False) -> None:
    parse_cookies(text)
    if path.exists() and not replace:
        raise ValueError("Cookie file exists; use --replace to rotate it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tiktok-secret-", dir=path.parent)
    try:
        os.close(fd)
        if os.name == "nt":
            identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
            sid = next(csv.reader(identity.strip().splitlines()))[1]
            subprocess.run(["icacls", temp, "/inheritance:r", "/grant:r", f"*{sid}:F"],
                           check=True, capture_output=True)
        else:
            os.chmod(temp, stat.S_IRUSR | stat.S_IWUSR)
        Path(temp).write_text(text.strip() + "\n", encoding="utf-8")
        # Do not replace an existing cookie unless explicitly requested.
        if replace:
            os.replace(temp, path)
        else:
            os.link(temp, path)
    except (subprocess.SubprocessError, OSError):
        raise ValueError("Cookie save failed; check access to the private secret file and Windows ACL permissions.") from None
    finally:
        Path(temp).unlink(missing_ok=True)
