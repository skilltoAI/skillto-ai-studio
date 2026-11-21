"""Local Metabase report registry and HTTP operations.

The table JSON remains authoritative. This module never writes to table files.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOCK = threading.RLock()
METABASE_URL = "http://127.0.0.1:3330"
TABLE_CATALOG = None


class ReportError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def data_root() -> Path:
    return Path(os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data"))).resolve()


def config_path() -> Path:
    return Path(os.environ.get("SKILLTO_REPORT_CONFIG", str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting" / "config.json")))


def config() -> dict:
    path = config_path()
    if not path.is_file():
        raise ReportError("Metabase 尚未配置；运行 reporting/setup_local.py", 503)
    return json.loads(path.read_text(encoding="utf-8"))


def _json_request(method: str, url: str, payload=None, headers=None):
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=raw, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        raise ReportError(f"Metabase HTTP {exc.code}: {body}", 502) from exc
    except (URLError, TimeoutError) as exc:
        raise ReportError(f"Metabase 不可用：{exc}", 503) from exc


_session = {"id": "", "at": 0.0}


def mb_request(method: str, path: str, payload=None, retry=True):
    if not path.startswith("/api/") or "://" in path:
        raise ReportError("无效 Metabase API 路径")
    with LOCK:
        if not _session["id"] or time.time() - _session["at"] > 3600:
            settings = config()
            login = _json_request("POST", METABASE_URL + "/api/session",
                                  {"username": settings["adminEmail"], "password": settings["adminPassword"]})
            _session.update(id=login["id"], at=time.time())
        headers = {"X-Metabase-Session": _session["id"]}
    try:
        return _json_request(method, METABASE_URL + path, payload, headers)
    except ReportError as exc:
        if "HTTP 401" not in str(exc) or not retry:
            raise
        with LOCK:
            _session["id"] = ""
        return mb_request(method, path, payload, False)


def _registry_path() -> Path:
    return data_root() / "reports" / "catalog.json"


def _read_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        return {"version": 1, "reports": [], "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_registry(value: dict):
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(4) + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _table_catalog():
    if TABLE_CATALOG is not None:
        return TABLE_CATALOG()
    path = data_root() / "catalog.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"knowledgeBases": []}


def _position(knowledge_base_id: str, project_id: str):
    catalog = _table_catalog()
    for kb in catalog["knowledgeBases"]:
        if kb["id"] == knowledge_base_id:
            for project in kb["projects"]:
                if project["id"] == project_id:
                    return kb, project
    raise ReportError("知识库或项目不存在")


def _entry(registry: dict, report_id: str):
    for entry in registry["reports"]:
        if entry["id"] == report_id:
            return entry
    raise ReportError("报表不存在", 404)


def _event(registry: dict, action: str, before, after):
    registry["history"].append({"id": str(uuid.uuid4()), "at": datetime.now(timezone.utc).isoformat(),
                                "action": action, "before": before, "after": after})


def catalog() -> dict:
    table_catalog = _table_catalog()
    with LOCK:
        registry = _read_registry()
    return {"knowledgeBases": table_catalog["knowledgeBases"],
            "reports": registry["reports"], "metabaseUrl": METABASE_URL,
            "configured": config_path().is_file()}


def lineage() -> dict:
    path = data_root() / "reports" / "lineage.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def get_report(report_id: str) -> dict:
    with LOCK:
        entry = dict(_entry(_read_registry(), report_id))
    result = {"report": entry}
    if entry["status"] == "active":
        result["dashboard"] = mb_request("GET", f"/api/dashboard/{entry['metabaseDashboardId']}")
    return result


def create_report(args: dict) -> dict:
    name = str(args.get("name", "")).strip()
    if not name or len(name) > 120:
        raise ReportError("报表名称须为 1–120 个字符")
    kb_id, project_id = args.get("knowledgeBaseId"), args.get("projectId")
    _position(kb_id, project_id)
    dashboard = mb_request("POST", "/api/dashboard", {"name": name, "description": args.get("description", "")})
    report = {"id": str(uuid.uuid4()), "name": name, "description": args.get("description", ""),
              "knowledgeBaseId": kb_id, "projectId": project_id,
              "sourceTableId": args.get("sourceTableId"),
              "metabaseDashboardId": dashboard["id"], "cardIds": [],
              "status": "active", "createdAt": datetime.now(timezone.utc).isoformat()}
    try:
        with LOCK:
            registry = _read_registry()
            registry["reports"].append(report)
            _event(registry, "create", None, report)
            _save_registry(registry)
    except Exception:
        mb_request("PUT", f"/api/dashboard/{dashboard['id']}", {"archived": True})
        raise
    return report


def update_report(args: dict) -> dict:
    with LOCK:
        registry = _read_registry()
        report = _entry(registry, args["reportId"])
        if report["status"] != "active":
            raise ReportError("已归档报表不能修改")
        before = dict(report)
        name = str(args.get("name", report["name"])).strip()
        if not name or len(name) > 120:
            raise ReportError("报表名称须为 1–120 个字符")
        kb_id = args.get("knowledgeBaseId", report["knowledgeBaseId"])
        project_id = args.get("projectId", report["projectId"])
        _position(kb_id, project_id)
        changes = {"name": name, "description": args.get("description", report["description"])}
        mb_request("PUT", f"/api/dashboard/{report['metabaseDashboardId']}", changes)
        report.update(changes, knowledgeBaseId=kb_id, projectId=project_id)
        _event(registry, "update", before, dict(report))
        _save_registry(registry)
        return dict(report)


def archive_report(args: dict, restore=False) -> dict:
    with LOCK:
        registry = _read_registry()
        report = _entry(registry, args["reportId"])
        desired = "active" if restore else "archived"
        if report["status"] == desired:
            return dict(report)
        before = dict(report)
        mb_request("PUT", f"/api/dashboard/{report['metabaseDashboardId']}", {"archived": not restore})
        report["status"] = desired
        _event(registry, "restore" if restore else "archive", before, dict(report))
        _save_registry(registry)
        return dict(report)


def content(args: dict) -> dict:
    action = args.get("operation")
    with LOCK:
        registry = _read_registry()
        report = _entry(registry, args["reportId"])
        if report["status"] != "active":
            raise ReportError("报表已归档")
        dash_id = report["metabaseDashboardId"]
        if action == "read":
            return {"dashboard": mb_request("GET", f"/api/dashboard/{dash_id}")}
        if action == "read_card":
            card_id = int(args["cardId"])
            if card_id not in report["cardIds"]:
                raise ReportError("图表不属于该报表")
            return {"card": mb_request("GET", f"/api/card/{card_id}")}
        if action == "create_card":
            payload = dict(args.get("card") or {})
            payload["dashboard_id"] = dash_id
            card = mb_request("POST", "/api/card", payload)
            report["cardIds"].append(card["id"])
            _event(registry, "create_card", None, {"reportId": report["id"], "cardId": card["id"]})
            _save_registry(registry)
            return {"card": card}
        if action in ("update_card", "archive_card"):
            card_id = int(args["cardId"])
            if card_id not in report["cardIds"]:
                raise ReportError("图表不属于该报表")
            payload = {"archived": True} if action == "archive_card" else dict(args.get("card") or {})
            card = mb_request("PUT", f"/api/card/{card_id}", payload)
            if action == "archive_card":
                report["cardIds"].remove(card_id)
            _event(registry, action, {"reportId": report["id"], "cardId": card_id}, payload)
            _save_registry(registry)
            return {"card": card}
        if action == "update_dashboard":
            payload = {k: v for k, v in (args.get("dashboard") or {}).items()
                       if k in {"dashcards", "parameters", "tabs", "description", "name"}}
            if not payload:
                raise ReportError("缺少仪表板更新内容")
            dashboard = mb_request("PUT", f"/api/dashboard/{dash_id}", payload)
            if "name" in payload:
                report["name"] = payload["name"]
            if "description" in payload:
                report["description"] = payload["description"]
            _event(registry, action, {"reportId": report["id"]}, payload)
            _save_registry(registry)
            return {"dashboard": dashboard}
    raise ReportError("未知图表操作")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def embed(report_id: str) -> dict:
    with LOCK:
        report = dict(_entry(_read_registry(), report_id))
    if report["status"] != "active":
        raise ReportError("报表已归档", 404)
    secret = config().get("embeddingSecret")
    if not secret:
        raise ReportError("Metabase guest embed 尚未启用", 503)
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(json.dumps({"resource": {"dashboard": report["metabaseDashboardId"]},
                               "params": {}, "exp": int(time.time()) + 600}, separators=(",", ":")).encode())
    message = (header + "." + payload).encode()
    signature = _b64(hmac.new(secret.encode(), message, hashlib.sha256).digest())
    return {"token": header + "." + payload + "." + signature,
            "metabaseUrl": METABASE_URL, "expiresIn": 600}


def dispatch(args: dict) -> dict:
    action = args.get("action")
    if action == "create":
        return create_report(args)
    if action == "update":
        return update_report(args)
    if action == "archive":
        return archive_report(args)
    if action == "restore":
        return archive_report(args, True)
    if action == "content":
        return content(args)
    raise ReportError("未知报表操作")
