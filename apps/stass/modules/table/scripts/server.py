"""Local semantic MCP tools for multimedia review tables."""

import json
import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(os.environ.get("SKILLTO_TABLE_ROOT", Path.home() / "skillto-table-data")).expanduser().resolve()
CATALOG = ROOT / "catalog.json"
TABLES = ROOT / "tables"
FIELD_TYPES = {"text", "number", "date", "boolean", "image", "video", "single_choice", "multiple_choice", "short_video_info"}
LINEAGE_FIELDS = ("sources", "methods", "rules", "destinations")


def empty_lineage():
    return {field: "" for field in LINEAGE_FIELDS}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def identifier():
    return str(uuid.uuid4())


def event(action, before=None, after=None, **extra):
    return {"id": identifier(), "at": now(), "action": action, "before": before, "after": after, **extra}


@contextmanager
def locked():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / ".write.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_json(path, default=None):
    if not path.exists():
        if default is None:
            raise ValueError("Item does not exist")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".table-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def catalog(*, include_modified=False):
    data = read_json(CATALOG, {"version": 2, "knowledgeBases": []})
    if include_modified:
        for base in data["knowledgeBases"]:
            for project in base["projects"]:
                for table in project["tables"]:
                    try:
                        modified = table_path(table["id"]).stat().st_mtime
                    except FileNotFoundError:
                        table["modifiedAt"] = None
                    else:
                        table["modifiedAt"] = datetime.fromtimestamp(modified, timezone.utc).isoformat()
    return data


def initialize_catalog():
    """Create the catalog only for a new, empty managed workspace."""
    with locked():
        if not CATALOG.exists() and not any(TABLES.glob("*.json")):
            write_json(CATALOG, {"version": 2, "knowledgeBases": []})


def report_catalog():
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("表格目录缺失，请从工作台备份恢复。") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("表格目录损坏，请检查工作台数据或从备份恢复。") from exc
    if not isinstance(data, dict) or not isinstance(data.get("knowledgeBases"), list):
        raise ValueError("表格目录格式无效，请检查工作台数据。")
    return data


def find(items, item_id, kind):
    match = next((item for item in items if item["id"] == item_id), None)
    if match is None:
        raise ValueError(f"{kind} not found")
    return match


def locate(data, level, args):
    if level == "knowledge_base":
        return data["knowledgeBases"]
    base = find(data["knowledgeBases"], args.get("knowledgeBaseId"), "Knowledge base")
    if level == "project":
        return base["projects"]
    project = find(base["projects"], args.get("projectId"), "Project")
    if level == "table":
        return project["tables"]
    raise ValueError("level must be knowledge_base, project, or table")


def table_path(table_id):
    try:
        uuid.UUID(table_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid table ID") from exc
    return TABLES / f"{table_id}.json"


def load_table(table_id):
    path = table_path(table_id)
    data = read_json(path)
    data.setdefault("fields", [])
    data.setdefault("tags", [])
    data.setdefault("rows", [])
    data.setdefault("history", [])
    data.setdefault("dataLineage", empty_lineage())
    return data


def table_workspace(args):
    action = args.get("action", "list")
    if action == "list":
        return catalog()
    level = args.get("level")
    with locked():
        data = catalog()
        items = locate(data, level, args)
        if action == "create":
            name = str(args.get("name", "")).strip()
            if not name:
                raise ValueError("Name is required")
            item = {"id": identifier(), "name": name, "description": args.get("description", "")}
            if level == "knowledge_base":
                item["projects"] = []
            elif level == "project":
                item["tables"] = []
            else:
                write_json(table_path(item["id"]), {"version": 2, "id": item["id"], "title": name,
                                                      "subtitle": "", "dataLineage": empty_lineage(),
                                                      "fields": [], "tags": [], "rows": [], "history": []})
            items.append(item)
            write_json(CATALOG, data)
            return item
        item = find(items, args.get("id"), level)
        if action == "rename":
            name = str(args.get("name", "")).strip()
            if not name:
                raise ValueError("Name is required")
            previous = dict(item)
            item["name"] = name
            if "description" in args:
                item["description"] = args["description"]
            if level == "table":
                table = load_table(item["id"])
                table["history"].append(event("rename_table", previous["name"], name))
                table["title"] = name
                write_json(table_path(item["id"]), table)
            write_json(CATALOG, data)
            return item
        if action == "delete":
            if level == "knowledge_base":
                has_content = bool(item["projects"])
            elif level == "project":
                has_content = bool(item["tables"])
            else:
                table = load_table(item["id"])
                has_content = bool(table["rows"] or table["fields"] or table["tags"] or table["history"])
            if has_content and not args.get("cascade"):
                raise ValueError("This item is not empty; set cascade=true to confirm deletion")
            table_ids = ([table["id"] for project in item["projects"] for table in project["tables"]]
                         if level == "knowledge_base" else [table["id"] for table in item["tables"]]
                         if level == "project" else [item["id"]])
            items.remove(item)
            write_json(CATALOG, data)
            for table_id in table_ids:
                table_path(table_id).unlink(missing_ok=True)
            return {"deleted": item["id"], "tablesDeleted": len(table_ids)}
        raise ValueError("action must be list, create, rename, or delete")


def table_define(args):
    with locked():
        table = load_table(args["tableId"])
        definitions = args.get("fields")
        if "fieldOrder" in args:
            order = args["fieldOrder"]
            by_name = {field["name"]: field for field in table["fields"]}
            current = list(by_name)
            if definitions is not None:
                raise ValueError("字段排序和定义修改需分别提交")
            if args.get("expectedFieldOrder", current) != current:
                raise ValueError("字段顺序已变化，请刷新后重试")
            if (not isinstance(order, list) or any(not isinstance(name, str) for name in order)
                    or len(order) != len(current) or set(order) != set(current)):
                raise ValueError("字段排序必须包含当前所有字段，且每个字段仅出现一次")
            rating_before = table.get("ratingBeforeField")
            next_rating_before = args.get("ratingBeforeField", rating_before)
            if "ratingBeforeField" in args:
                if args.get("expectedRatingBeforeField") != rating_before:
                    raise ValueError("评分列位置已变化，请刷新后重试")
                if next_rating_before is not None and (not isinstance(next_rating_before, str) or next_rating_before not in by_name):
                    raise ValueError("评分列位置必须是当前字段名或空")
            if order != current or next_rating_before != rating_before:
                table["fields"] = [by_name[name] for name in order]
                if order != current:
                    table["history"].append(event("reorder_fields", current, order))
                if next_rating_before != rating_before:
                    table["ratingBeforeField"] = next_rating_before
                    table["history"].append(event("reorder_rating", rating_before, next_rating_before))
                write_json(table_path(args["tableId"]), table)
            return table["fields"]
        if definitions is None:
            return table["fields"]
        names = set()
        for field in definitions:
            name = field.get("name")
            if not name or name in names or field.get("type") not in FIELD_TYPES:
                raise ValueError("Each field needs a unique name and supported type")
            if field["type"] in {"single_choice", "multiple_choice"} and not isinstance(field.get("options"), list):
                raise ValueError("Choice fields need an options list")
            if "candidateGroup" in field and (field["type"] != "image" or not isinstance(field["candidateGroup"], str) or not field["candidateGroup"].strip()):
                raise ValueError("Candidate groups require a nonempty string on image fields")
            names.add(name)
        before = table["fields"]
        table["fields"] = definitions
        table["history"].append(event("define_fields", before, definitions))
        write_json(table_path(args["tableId"]), table)
        return definitions


def table_lineage(args):
    """Read or update table-level data provenance without touching rows."""
    table_id = args["tableId"]
    with locked():
        table = load_table(table_id)
        current = table["dataLineage"]
        if "dataLineage" not in args:
            return current
        incoming = args["dataLineage"]
        if not isinstance(incoming, dict) or any(key not in LINEAGE_FIELDS for key in incoming):
            raise ValueError("dataLineage must contain only sources, methods, rules, destinations")
        if any(not isinstance(value, str) for value in incoming.values()):
            raise ValueError("Every dataLineage value must be text")
        updated = {field: incoming.get(field, current.get(field, "")).strip() for field in LINEAGE_FIELDS}
        if updated != current:
            table["dataLineage"] = updated
            table["history"].append(event("update_data_lineage", current, updated))
            write_json(table_path(table_id), table)
        return updated


def validate_row_fields(table, values):
    if not isinstance(values, dict):
        raise ValueError("fields must be an object")
    types = {field["name"]: field["type"] for field in table["fields"]}
    for name, value in values.items():
        if name == "selectedCandidateImages":
            if not isinstance(value, list) or any(not isinstance(item, str) or item not in candidate_image_fields(table) for item in value):
                raise ValueError("Selected candidate images must name this table's candidate image fields")
        if types.get(name) != "short_video_info":
            continue
        if not isinstance(value, list):
            raise ValueError(f"{name} must be a list of short videos")
        for video in value:
            if not isinstance(video, dict) or not video.get("id") or not video.get("title"):
                raise ValueError(f"{name} videos need an id and title")
            url = urlparse(str(video.get("videoUrl", "")))
            if url.scheme not in {"http", "https"} or not url.netloc:
                raise ValueError(f"{name} videos need an HTTP source URL")
            for metric in ("playCount", "likeCount", "collectCount", "shareCount", "commentCount"):
                count = video.get(metric)
                if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
                    raise ValueError(f"{metric} must be a nonnegative integer or null")


def candidate_image_fields(table):
    return {field["name"] for field in table["fields"]
            if field["type"] == "image" and field.get("candidateGroup")}


def matches_filter(row, clause):
    field = clause.get("field")
    actual = row.get("fields", {}).get(field)
    if field == "score":
        actual = row.get("rating", {}).get("score")
    operator = clause.get("operator", "eq")
    value = clause.get("value")
    if operator == "eq":
        return actual == value
    if operator == "contains":
        return str(value).casefold() in str(actual or "").casefold()
    if operator == "in":
        return actual in value if isinstance(value, list) else False
    if actual is None:
        return False
    if operator == "between":
        return isinstance(value, list) and len(value) == 2 and value[0] <= actual <= value[1]
    if operator == "gte":
        return actual >= value
    if operator == "lte":
        return actual <= value
    raise ValueError("Unsupported filter operator")


def table_query(args):
    table = load_table(args["tableId"])
    rows = table["rows"]
    search = str(args.get("search", "")).casefold()
    if search:
        rows = [row for row in rows if search in " ".join(map(str, row.get("fields", {}).values())).casefold()]
    for clause in args.get("filters", []):
        rows = [row for row in rows if matches_filter(row, clause)]
    if args.get("scoreStatus") == "scored":
        rows = [row for row in rows if row.get("rating", {}).get("score") is not None]
    elif args.get("scoreStatus") == "unscored":
        rows = [row for row in rows if row.get("rating", {}).get("score") is None]
    if args.get("tagIds"):
        rows = [row for row in rows if set(args["tagIds"]).issubset(row.get("tagIds", []))]
    if args.get("mediaType"):
        rows = [row for row in rows if any(media.get("type") == args["mediaType"] for media in row.get("media", []))]
    return {"table": {key: table[key] for key in ("id", "title", "fields", "tags")}, "count": len(rows), "rows": rows}


def table_save_row(args):
    action = args.get("action", "create")
    with locked():
        table = load_table(args["tableId"])
        if action == "create":
            validate_row_fields(table, args.get("fields", {}))
            timestamp = now()
            row = {"id": identifier(), "fields": args.get("fields", {}), "media": args.get("media", []),
                   "tagIds": [], "rating": {"score": None, "note": ""}, "history": [],
                   "createdAt": timestamp, "updatedAt": timestamp}
            row["history"].append(event("create_row", None, {"fields": row["fields"], "media": row["media"]}))
            table["rows"].append(row)
        else:
            row = find(table["rows"], args.get("rowId"), "Row")
            if action == "update":
                validate_row_fields(table, args.get("fields", {}))
                expected = args.get("expectedFields", {})
                if not isinstance(expected, dict) or not expected.keys() <= args.get("fields", {}).keys():
                    raise ValueError("比较值必须对应本次修改的字段")
                if any(row["fields"].get(key) != value for key, value in expected.items()):
                    raise ValueError("此字段已被修改，请核对最新值后再保存")
                if "selectedCandidateImages" in args.get("fields", {}):
                    raise ValueError("Use table_select_candidates to change selected images")
                candidate_fields = candidate_image_fields(table)
                for key in ("fields", "media"):
                    if key in args:
                        if key == "fields":
                            for field, value in args[key].items():
                                before = row["fields"].get(field)
                                row["fields"][field] = value
                                row["history"].append(event("edit_field", before, value, field=field))
                                if field in candidate_fields and before != value:
                                    selected = row["fields"].get("selectedCandidateImages", [])
                                    if field in selected:
                                        row["fields"]["selectedCandidateImages"] = [name for name in selected if name != field]
                                        row["history"].append(event("select_candidate_images", selected,
                                                                    row["fields"]["selectedCandidateImages"]))
                        else:
                            before = row["media"]
                            row["media"] = args[key]
                            row["history"].append(event("edit_media", before, row["media"]))
                row["updatedAt"] = now()
            elif action == "delete":
                label = next(iter(row.get("fields", {}).values()), row["id"])
                table["history"].append(event("delete_row", row, None, rowId=row["id"], rowLabel=str(label)))
                table["rows"].remove(row)
            else:
                raise ValueError("action must be create, update, or delete")
        write_json(table_path(args["tableId"]), table)
        return {"deleted": args["rowId"]} if action == "delete" else row


def table_review(args):
    with locked():
        table = load_table(args["tableId"])
        row = find(table["rows"], args["rowId"], "Row")
        if "score" in args or "note" in args:
            score = args.get("score", row["rating"]["score"])
            if score is not None and (type(score) not in (int, float) or not 0.5 <= score <= 5 or score * 2 != int(score * 2)):
                raise ValueError("Score must be 0.5 to 5 in half-star steps, or null")
            before = dict(row["rating"])
            row["rating"] = {"score": score, "note": args.get("note", before["note"])}
            row["history"].append(event("rate_row", before, row["rating"]))
        if "tagIds" in args:
            valid = {tag["id"] for tag in table["tags"]}
            if not isinstance(args["tagIds"], list) or not set(args["tagIds"]).issubset(valid):
                raise ValueError("Tags must belong to this table")
            before = row.get("tagIds", [])
            row["tagIds"] = list(dict.fromkeys(args["tagIds"]))
            row["history"].append(event("set_row_tags", before, row["tagIds"]))
        row["updatedAt"] = now()
        write_json(table_path(args["tableId"]), table)
        return row


def table_select_candidates(args):
    with locked():
        table = load_table(args["tableId"])
        row = find(table["rows"], args["rowId"], "Row")
        selected = args.get("imageFields")
        if not isinstance(selected, list) or any(not isinstance(name, str) for name in selected):
            raise ValueError("imageFields must be a list of candidate image field names")
        available = candidate_image_fields(table)
        if any(name not in available or not row["fields"].get(name) for name in selected):
            raise ValueError("Selected candidates must be populated candidate image fields in this row")
        selected = list(dict.fromkeys(selected))
        before = row["fields"].get("selectedCandidateImages", [])
        if before != selected:
            row["fields"]["selectedCandidateImages"] = selected
            row["history"].append(event("select_candidate_images", before, selected))
            row["updatedAt"] = now()
            write_json(table_path(args["tableId"]), table)
        return row


def table_tags(args):
    action = args.get("action", "list")
    if action == "list":
        return load_table(args["tableId"])["tags"]
    with locked():
        table = load_table(args["tableId"])
        tags = table["tags"]
        if action == "create":
            name = str(args.get("name", "")).strip()
            if not name:
                raise ValueError("Tag name is required")
            if any(item["name"].casefold() == name.casefold() for item in tags):
                raise ValueError("Tag name already exists in this table")
            tag = {"id": identifier(), "name": name, "color": args.get("color", "#2d7d69")}
            tags.append(tag)
            table["history"].append(event("create_tag", None, tag))
        else:
            tag = find(tags, args.get("tagId"), "Tag")
            before = dict(tag)
            if action == "rename":
                name = str(args.get("name", "")).strip()
                if not name:
                    raise ValueError("Tag name is required")
                if any(item["id"] != tag["id"] and item["name"].casefold() == name.casefold() for item in tags):
                    raise ValueError("Tag name already exists in this table")
                tag["name"] = name
                if "color" in args:
                    tag["color"] = args["color"]
                table["history"].append(event("rename_tag", before, dict(tag)))
            elif action == "delete":
                for row in table["rows"]:
                    if tag["id"] in row.get("tagIds", []):
                        previous = row["tagIds"][:]
                        row["tagIds"].remove(tag["id"])
                        row["history"].append(event("remove_deleted_tag", previous, row["tagIds"][:]))
                        row["updatedAt"] = now()
                tags.remove(tag)
                table["history"].append(event("delete_tag", before, None))
            else:
                raise ValueError("action must be list, create, rename, or delete")
        write_json(table_path(args["tableId"]), table)
        return {"deleted": before["id"]} if action == "delete" else tag


TOOLS = {
    "table_workspace": ("Browse or manage knowledge bases, projects, and tables.", table_workspace,
                        {"action": "list|create|rename|delete", "level": "knowledge_base|project|table",
                         "knowledgeBaseId": "parent ID for project/table", "projectId": "parent ID for table",
                         "id": "item ID for rename/delete", "name": "display name", "cascade": "confirm nonempty deletion"}),
    "table_define": ("Read or set a table's business field definitions.", table_define,
                     {"tableId": "table ID", "fields": "optional list of {name,label,type,options?}",
                      "fieldOrder": "optional permutation of existing field names", "expectedFieldOrder": "optional order originally read by the editor",
                      "ratingBeforeField": "optional field before which to place the rating column, or null for the end",
                      "expectedRatingBeforeField": "rating position originally read by the editor, or null"}),
    "table_lineage": ("Read or update a table's data sources, collection/organization methods, rules, and destinations.", table_lineage,
                      {"tableId": "table ID", "dataLineage": "optional object with sources, methods, rules, destinations"}),
    "table_query": ("Find table rows with text, field, date, score, tag, or media filters.", table_query,
                    {"tableId": "table ID", "search": "text", "filters": "list of {field,operator,value}",
                     "scoreStatus": "scored|unscored", "tagIds": "all required tag IDs", "mediaType": "image|video"}),
    "table_save_row": ("Create, edit, or delete one business record.", table_save_row,
                       {"tableId": "table ID", "action": "create|update|delete", "rowId": "row ID for update/delete",
                        "fields": "business field values", "media": "image/video entries", "expectedFields": "optional previous values of fields being updated"}),
    "table_review": ("Rate a row and assign its table-specific tags.", table_review,
                     {"tableId": "table ID", "rowId": "row ID", "score": "0.5-5 in half-star steps, or null", "note": "rating reason",
                      "tagIds": "complete list of assigned tag IDs"}),
    "table_select_candidates": ("Set the human-selected candidate images for one row without changing its other fields.",
                                table_select_candidates,
                                {"tableId": "table ID", "rowId": "row ID",
                                 "imageFields": "complete list of selected candidate image field names; empty list clears"}),
    "table_tags": ("List, create, rename, or delete tags belonging to one table.", table_tags,
                   {"tableId": "table ID", "action": "list|create|rename|delete", "tagId": "tag ID",
                    "name": "tag name", "color": "CSS color"}),
}


from browser_profiles import browser_call
TOOLS['browser_profiles'] = ('Manage local Chrome usernames and persistent environments. Requires local launcher service; never AMD-PAD.', browser_call,
    {'action': 'list|create|rename|delete|launch|close', 'userId': 'stable user ID', 'username': 'exact username alternative to userId',
     'name': 'new display name for create/rename', 'confirmName': 'exact current name required for delete; close first'})
TOOLS['browser_action'] = ('Operate inside a local user Chrome: pages, new_page, navigate, snapshot (accessible tree), click, fill, press, evaluate (JavaScript), screenshot, close_page. Use pageId from pages and selectors from snapshot.', browser_call,
    {'action': 'pages|new_page|navigate|snapshot|click|fill|press|evaluate|screenshot|close_page', 'userId': 'stable browser user ID',
     'username': 'exact username alternative', 'pageId': 'page ID; defaults to first page', 'url': 'HTTP(S) URL',
     'selector': 'Playwright selector, e.g. role=button[name="Login"]', 'text': 'fill text', 'key': 'key e.g. Enter',
     'expression': 'JavaScript expression executed in this user page'})


def tool_schema(name, description, hints):
    properties = {key: {"description": hint, "type": "boolean" if key == "cascade" else
                          "array" if key in {"fields", "filters", "tagIds", "media", "imageFields"} else
                          "object" if key == "fieldsValues" else "string"}
                  for key, hint in hints.items()}
    if name == "table_save_row":
        properties["fields"] = {"type": "object", "description": hints["fields"], "additionalProperties": True}
        properties["expectedFields"] = {"type": "object", "description": hints["expectedFields"], "additionalProperties": True}
        properties["media"] = {"type": "array", "items": {"type": "object"}}
    if name == "table_define":
        properties["fields"] = {"type": "array", "items": {"type": "object"}}
        for key in ("fieldOrder", "expectedFieldOrder"):
            properties[key] = {"type": "array", "items": {"type": "string"}, "description": hints[key]}
        for key in ("ratingBeforeField", "expectedRatingBeforeField"):
            properties[key] = {"type": ["string", "null"], "description": hints[key]}
    if name == "table_lineage":
        properties["dataLineage"] = {"type": "object", "properties": {field: {"type": "string"} for field in LINEAGE_FIELDS},
                                     "additionalProperties": False}
    if name == "table_query":
        properties["filters"] = {"type": "array", "items": {"type": "object"}}
    if name == "table_review":
        properties["score"] = {"type": ["number", "null"], "minimum": 0.5, "maximum": 5, "multipleOf": 0.5}
    if name == "table_select_candidates":
        properties["imageFields"] = {"type": "array", "items": {"type": "string"}}
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": ["action"] if name.startswith("browser_") else [] if name == "table_workspace" else
                                        ["tableId", "rowId", "imageFields"] if name == "table_select_candidates" else ["tableId"]}}


def dispatch(request):
    method = request.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "skillto-ai-studio-table", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [tool_schema(name, description, hints) for name, (description, _, hints) in TOOLS.items()]}
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        if name not in TOOLS:
            raise ValueError("Unknown tool")
        result = TOOLS[name][1](params.get("arguments", {}))
        if name == "browser_action" and params.get("arguments", {}).get("action") == "screenshot":
            return {"content": [{"type": "image", "data": result["base64"], "mimeType": result["mimeType"]}]}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    raise ValueError("Unknown method")


def main():
    if os.environ.get('SKILLTO_TABLE_API_URL'):
        from remote_client import main as remote_main
        return remote_main()
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if "id" not in request:
                continue
            response = {"jsonrpc": "2.0", "id": request["id"], "result": dispatch(request)}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32603, "message": str(exc)}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
