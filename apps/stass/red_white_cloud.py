"""Public Skillto.ai topic summaries. This client never fetches paid content."""
import json
import re
import threading
from datetime import datetime, timezone
from urllib.request import build_opener, HTTPRedirectHandler, Request


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


BASE = "https://www.skillto.ai/api/v1/red-white/topics"
TOPIC = re.compile(r"sto_[a-z0-9][a-z0-9_-]{1,79}")
_lock = threading.Lock()
_snapshot = None


def read_json(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Skillto-AI-Studio/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=6) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000 or response.headers.get_content_type() != "application/json":
            raise ValueError("Invalid official topic response")
        return json.loads(body)


def official_list():
    global _snapshot
    with _lock:
        now = datetime.now(timezone.utc)
        if _snapshot and _snapshot[0] > now:
            return _snapshot[1]
        data = read_json(BASE)
        if data.get("view") != "cloud" or data.get("schemaVersion") != 1:
            raise ValueError("Invalid official catalog")
        expires = datetime.fromisoformat(data["cloudValidUntil"].replace("Z", "+00:00"))
        generated = datetime.fromisoformat(data["generatedAt"].replace("Z", "+00:00"))
        if not generated <= now < expires or (expires-generated).total_seconds() > 300:
            raise ValueError("Expired official catalog")
        ids = set()
        free = set()
        rows = []
        for row in data["topics"]:
            key = row["id"]
            if (not TOPIC.fullmatch(key) or key in ids or row.get("origin") != "cloud"
                    or row.get("renderMode") != "iframe" or row.get("requiresLogin") is not False
                    or row["access"] not in ("free", "paid") or not isinstance(row["title"], str)):
                raise ValueError("Invalid official topic")
            ids.add(key)
            if row["access"] == "free":
                free.add(key)
            elif row["itemCount"] is not None:
                raise ValueError("Unexpected paid count")
            rows.append({k: row[k] for k in ("id","title","access","position","revision","itemCount")})
        default = data["defaultTopicId"]
        if (rows and default not in free) or (not rows and default is not None):
            raise ValueError("Invalid default topic")
        result = {"topics": rows, "defaultTopicId": default}
        _snapshot = expires, result
        return result


def official_embed(key):
    if not TOPIC.fullmatch(key) or key not in {r["id"] for r in official_list()["topics"]}:
        raise ValueError("Unknown official topic")
    data = read_json(BASE + "/" + key)
    path = "/red-white/topics/" + key
    if (data.get("schemaVersion") != 1 or data.get("kind") != "cloud-embed" or data.get("topic",{}).get("id") != key
            or data.get("embed") != {"url":"https://www.skillto.ai/red-white/embed/topics/"+key,
                                    "externalUrl":"https://www.skillto.ai"+path,"protocolVersion":1}):
        raise ValueError("Invalid embed descriptor")
    return data["embed"]
