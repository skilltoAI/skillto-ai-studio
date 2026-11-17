"""Provision the loopback Metabase instance and protected local credentials."""
from __future__ import annotations

import json
import hashlib
import os
import secrets
import subprocess
import sys
import time
import zipfile
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting"
CONFIG = CONFIG_DIR / "config.json"
ENV = CONFIG_DIR / "compose.env"
URL = "http://127.0.0.1:3330"


def request(method: str, path: str, body=None, session=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if session:
        headers["X-Metabase-Session"] = session
    req = Request(URL + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=30) as response:
        raw = response.read()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode("utf-8")


def settings():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
    else:
        value = {"adminEmail": "admin@skillto.local", "adminPassword": secrets.token_urlsafe(30) + "8!",
                 "dbPassword": secrets.token_urlsafe(30)}
        CONFIG.write_text(json.dumps(value, indent=2), encoding="utf-8")
    ENV.write_text("REPORT_DB_PASSWORD=" + value["dbPassword"] + "\n", encoding="utf-8")
    if os.name == "nt":
        identity = subprocess.check_output(["whoami", "/user"], text=True).strip().splitlines()[-1].split()[-1]
        for path in (CONFIG_DIR, CONFIG, ENV):
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{identity}:(OI)(CI)F" if path == CONFIG_DIR else f"*{identity}:F"],
                           capture_output=True, text=True, check=True)
    return value


def main():
    value = settings()
    compose = ["docker", "compose", "--env-file", str(ENV), "-f", str(HERE / "compose.yaml")]
    official = subprocess.run(["docker", "image", "inspect", "metabase/metabase:v0.64.3.x"],
                              capture_output=True)
    if official.returncode:
        local = subprocess.run(["docker", "image", "inspect", "skillto/metabase-oss:v0.64.3.6"],
                               capture_output=True)
        if local.returncode:
            jar = HERE.parents[2] / "runtime" / "reporting" / "metabase.jar"
            java = subprocess.run(["docker", "image", "inspect", "mirror.gcr.io/eclipse-temurin:21-jre-alpine"],
                                  capture_output=True)
            if not jar.is_file() or jar.stat().st_size != 712928220 or not zipfile.is_zipfile(jar) or java.returncode:
                raise RuntimeError("Metabase image missing; pull the official image or provide the official JAR and Java image")
            with jar.open("rb") as file:
                digest = hashlib.file_digest(file, "sha256").hexdigest()
            if digest != "fb986511fd215246464b4847f34109da14d373841bb0e439655f36d60aec3e7d":
                raise RuntimeError("Official Metabase JAR checksum does not match the verified release")
            build = subprocess.run(["docker", "build", "--pull=false", "-f", str(HERE / "Dockerfile.jar"),
                                    "-t", "skillto/metabase-oss:v0.64.3.6", str(jar.parent)],
                                   capture_output=True, text=True)
            if build.returncode:
                raise RuntimeError("Local Metabase image build failed: " + build.stderr[-1200:])
        compose += ["-f", str(HERE / "compose.jar.yaml")]
    start = subprocess.run(compose + ["up", "-d", "--quiet-pull"], capture_output=True, text=True)
    if start.returncode:
        raise RuntimeError("Docker Compose failed: " + start.stderr[-1200:])
    for _ in range(90):
        try:
            if request("GET", "/api/health").get("status") == "ok":
                break
        except (HTTPError, URLError, TimeoutError, ConnectionError, HTTPException):
            pass
        time.sleep(5)
    else:
        raise RuntimeError("Metabase health check timed out")
    properties = request("GET", "/api/session/properties")
    if not properties.get("has-user-setup"):
        request("POST", "/api/setup", {"token": properties["setup-token"],
                                     "user": {"first_name": "SkillTo", "last_name": "Reports",
                                              "email": value["adminEmail"], "password": value["adminPassword"]},
                                     "prefs": {"site_name": "SkillTo 报表", "allow_tracking": False}})
    session = request("POST", "/api/session", {"username": value["adminEmail"], "password": value["adminPassword"]})["id"]
    databases = request("GET", "/api/database", session=session)
    listed = databases.get("data", []) if isinstance(databases, dict) else databases
    existing = next((d for d in listed if d.get("name") == "SkillTo Reports"), None)
    if not existing:
        existing = request("POST", "/api/database", {
            "name": "SkillTo Reports", "engine": "postgres",
            "details": {"host": "postgres", "port": 5432, "dbname": "reports",
                        "user": "report_admin", "password": value["dbPassword"], "ssl": False},
            "is_full_sync": True, "is_on_demand": False}, session)
    value["metabaseDatabaseId"] = existing["id"]
    request("PUT", "/api/setting/report-timezone", {"value": "Asia/Shanghai"}, session)
    request("PUT", "/api/setting/site-locale", {"value": "zh-CN"}, session)
    for key in ("enable-embedding-static", "enable-embedding-simple"):
        try:
            request("PUT", "/api/setting/" + key, {"value": True}, session)
        except HTTPError:
            if key == "enable-embedding-static":
                raise
    secret = request("GET", "/api/setting/embedding-secret-key", session=session)
    if isinstance(secret, dict):
        secret = secret.get("value")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Metabase did not return an embedding secret")
    value["embeddingSecret"] = secret
    CONFIG.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print("Metabase ready at", URL, "database id", value["metabaseDatabaseId"])
    print("Credentials stored in", CONFIG)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        raise
