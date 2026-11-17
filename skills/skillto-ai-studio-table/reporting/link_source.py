"""Record the local report destinations on the authoritative account table."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

TABLE_ID = "56fa8754-8d40-4225-8541-0be4729ade73"
BASE = "http://127.0.0.1:8880"


def post(body):
    request = Request(BASE + "/api/lineage", method="POST",
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    with urlopen(BASE + "/api/reports/catalog", timeout=30) as response:
        catalog = json.load(response)
    reports = [item for item in catalog["reports"]
               if item["status"] == "active" and item.get("sourceTableId") == TABLE_ID]
    if len(reports) != 2:
        raise ValueError("Expected two active account reports")
    current = post({"tableId": TABLE_ID})
    marker = "2026-11-07 本地 Metabase 报表："
    addition = marker + "；".join(
        item["name"] + "（8880 报表 ID " + item["id"] +
        "，Metabase 仪表板 ID " + str(item["metabaseDashboardId"]) + "）"
        for item in reports)
    destinations = current.get("destinations", "")
    if marker not in destinations:
        current["destinations"] = destinations.rstrip() + "\n" + addition
        post({"tableId": TABLE_ID, "dataLineage": current})
    print("Source lineage includes", len(reports), "local report destinations")


if __name__ == "__main__":
    main()
