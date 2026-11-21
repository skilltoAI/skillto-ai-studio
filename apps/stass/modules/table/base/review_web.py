from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import os
ROOT = Path(os.environ["STASS_RESOURCE_ROOT"]).resolve()
_STORE = None
def table_store():
    if _STORE is None: raise RuntimeError("Table store was not injected")
    return _STORE


ASSETS = Path(__file__).parent / "review_assets"
SCHEMA_ASSETS = Path(__file__).resolve().parents[1] / "assets"


class ReviewHandler(BaseHTTPRequestHandler):
    db: Database

    def respond(self, data: bytes, content_type: str, status: int = 200, attachment: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https: data:; media-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(data)

    def respond_media(self, video_id: str):
        path = ROOT / "downloads" / "douyin_originals" / f"{video_id}.mp4"
        self.respond_video_path(path)

    def respond_video_path(self, path: Path):
        if not path.is_file():
            self.respond_json({"error": "Video file not found"}, 404)
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
            if not match:
                self.respond_json({"error": "Invalid media range"}, 416)
                return
            start = int(match.group(1))
            end = min(int(match.group(2)), end) if match.group(2) else end
            if start >= size or end < start:
                self.respond_json({"error": "Media range unavailable"}, 416)
                return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def respond_generated_image(self, table_id: str, filename: str):
        path = ROOT / "downloads" / "generated_table_images" / table_id / filename
        if not path.is_file():
            self.respond_json({"error": "Image file not found"}, 404)
            return
        content_type = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}[path.suffix]
        self.respond(path.read_bytes(), content_type)

    def respond_json(self, payload, status: int = 200):
        self.respond(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            media_match = re.fullmatch(r"/media/(\d{15,22})\.mp4", parsed.path)
            if media_match:
                self.respond_media(media_match.group(1))
                return
            artifact_match = re.fullmatch(r"/artifacts/omni_depth/(timeline_first_clip_0000_0450_(?:color|depth)\.mp4|jianying_clip1_t000000_004633_(?:color|depth)\.mp4|(?:white_model_reference|white_model_reference_latest|omni_first_clip_storyboard)\.png)", parsed.path)
            if artifact_match:
                path = ROOT / "outputs" / "omni_depth" / artifact_match.group(1)
                if path.suffix == ".mp4":
                    self.respond_video_path(path)
                elif path.is_file():
                    self.respond(path.read_bytes(), "image/png")
                else:
                    self.respond_json({"error": "Image file not found"}, 404)
                return
            generated_match = re.fullmatch(
                r"/generated/([0-9a-f-]{36})/([a-z0-9_-]+\.(?:png|jpg|webp))", parsed.path
            )
            if generated_match:
                self.respond_generated_image(generated_match.group(1), generated_match.group(2))
                return
            if parsed.path == "/research":
                page = (ASSETS / "index.html").read_text(encoding="utf-8")
                page = page.replace('</head>', '<link rel="stylesheet" href="/schema-controls.css"><script src="/schema-controls.js" defer></script><script src="/schema-editor.js" defer></script></head>')
                self.respond(page.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path in {"/schema-controls.js", "/schema-controls.css"}:
                mime = "text/javascript" if parsed.path.endswith(".js") else "text/css"
                self.respond((SCHEMA_ASSETS / parsed.path[1:]).read_bytes(), mime + "; charset=utf-8")
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/schema-editor.js": ("schema-editor.js", "text/javascript; charset=utf-8"),
                      "/short-videos": ("short-videos.html", "text/html; charset=utf-8"),
                      "/short-videos.js": ("short-videos.js", "text/javascript; charset=utf-8"),
                      "/short-videos.css": ("short-videos.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/adjustments.css": ("adjustments.css", "text/css; charset=utf-8")}
            if parsed.path in assets:
                filename, content_type = assets[parsed.path]
                self.respond((ASSETS / filename).read_bytes(), content_type)
                return
            store = table_store()
            query = parse_qs(parsed.query)
            if parsed.path == "/api/catalog":
                self.respond_json(store.catalog(include_modified=True))
            elif parsed.path == "/api/table":
                self.respond_json(store.load_table(query["id"][0]))
            elif parsed.path == "/api/export":
                table = store.load_table(query["id"][0])
                self.respond(json.dumps(table, ensure_ascii=False, indent=2).encode("utf-8"),
                             "application/json; charset=utf-8", attachment="review-state.json")
            else:
                self.respond_json({"error": "Not found"}, 404)
        except (KeyError, ValueError) as exc:
            self.respond_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.respond_json({"error": str(exc)}, 500)

    def do_POST(self):
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected JSON")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 10_000_000:
                raise ValueError("Request size is invalid")
            args = json.loads(self.rfile.read(length))
            store = table_store()
            routes = {"/api/workspace": store.table_workspace, "/api/define": store.table_define,
                      "/api/row": store.table_save_row, "/api/review": store.table_review,
                      "/api/candidates": store.table_select_candidates,
                      "/api/tags": store.table_tags}
            if self.path in routes:
                result = routes[self.path](args)
            elif self.path == "/api/sync":
                raise ValueError("Collection refresh must use the configured report module")
            elif self.path == "/api/import":
                result = self.import_table(store, args)
            else:
                self.respond_json({"error": "Not found"}, 404)
                return
            self.respond_json(result)
        except (KeyError, ValueError, TypeError) as exc:
            self.respond_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.respond_json({"error": str(exc)}, 500)

    @staticmethod
    def import_table(store, args):
        table_id = args["tableId"]
        incoming = args["data"]
        if isinstance(incoming, list):
            incoming = {"rows": incoming}
        if not isinstance(incoming, dict) or not isinstance(incoming.get("rows"), list):
            raise ValueError("Import needs a JSON object with rows")
        with store.locked():
            current = store.load_table(table_id)
            definitions = incoming.get("fields", current["fields"])
            tags = incoming.get("tags", current["tags"])
            if not isinstance(definitions, list) or not isinstance(tags, list):
                raise ValueError("Field and tag definitions must be lists")
            names = [field.get("name") for field in definitions if isinstance(field, dict)]
            if len(names) != len(definitions) or len(set(names)) != len(names) or any(field.get("type") not in store.FIELD_TYPES for field in definitions):
                raise ValueError("Imported field definitions are invalid")
            tag_ids = [tag.get("id") for tag in tags if isinstance(tag, dict)]
            if len(tag_ids) != len(tags) or len(set(tag_ids)) != len(tag_ids):
                raise ValueError("Imported tag definitions are invalid")
            validation_table = {**current, "fields": definitions}
            rows = incoming["rows"]
            normalized = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("Each row must be an object")
                if "fields" not in row:
                    row = {"fields": row}
                store.validate_row_fields(validation_table, row["fields"])
                if not set(row.get("tagIds", [])).issubset(tag_ids):
                    raise ValueError("Imported row references an unknown tag")
                normalized.append({**row, "id": row.get("id") or store.identifier(), "fields": row["fields"],
                                   "media": row.get("media", []), "tagIds": row.get("tagIds", []),
                                   "rating": row.get("rating", {"score": None, "note": ""}),
                                   "history": row.get("history", []), "createdAt": row.get("createdAt") or store.now(),
                                   "updatedAt": row.get("updatedAt") or store.now()})
            before = {"rowCount": len(current["rows"])}
            lineage = incoming.get("dataLineage", current.get("dataLineage", store.empty_lineage()))
            if not isinstance(lineage, dict) or any(key not in store.LINEAGE_FIELDS for key in lineage):
                raise ValueError("Imported dataLineage is invalid")
            if any(not isinstance(value, str) for value in lineage.values()):
                raise ValueError("Imported dataLineage values must be text")
            current["dataLineage"] = {key: lineage.get(key, "") for key in store.LINEAGE_FIELDS}
            current["fields"] = definitions
            current["tags"] = tags
            current["rows"] = normalized
            current["history"] = list(incoming.get("history", current["history"]))
            current["history"].append(store.event("import_rows", before, {"rowCount": len(normalized)}))
            store.write_json(store.table_path(table_id), current)
        return {"imported": len(normalized)}

    def log_message(self, format, *args):
        return
