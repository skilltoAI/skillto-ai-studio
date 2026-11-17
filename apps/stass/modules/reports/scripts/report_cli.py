"""Small client for the local report service. JSON payloads are read from files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8880"


def send(path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(BASE + path, data=data, method="POST" if payload is not None else "GET",
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=90) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(error.read().decode("utf-8", "replace")) from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list", "get", "create", "update", "archive", "restore", "content", "refresh"])
    parser.add_argument("--id", help="Stable report UUID")
    parser.add_argument("--json", help="Path to JSON body for create, update or content")
    args = parser.parse_args()
    if args.command == "list":
        result = send("/api/reports/catalog")
    elif args.command == "get":
        result = send("/api/reports/item?" + urlencode({"id": args.id}))
    elif args.command == "refresh":
        result = send("/api/reports/refresh", {})
    else:
        body = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else {}
        body["action"] = args.command
        if args.id:
            body["reportId"] = args.id
        result = send("/api/reports", body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
