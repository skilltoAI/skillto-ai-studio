"""Back up the source table, report workspace, and both PostgreSQL databases."""
from __future__ import annotations

import os
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SKILLTO_TABLE_ROOT", str(Path.home() / "skillto-table-data")))
DEST = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "backups"
ENV = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SkillToTable" / "reporting" / "compose.env"
TABLE_ID = "56fa8754-8d40-4225-8541-0be4729ade73"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / ("reports-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT / "catalog.json", "tables/catalog.json")
        archive.write(ROOT / "tables" / (TABLE_ID + ".json"), "tables/" + TABLE_ID + ".json")
        for path in (ROOT / "reports").rglob("*"):
            if path.is_file():
                archive.write(path, str(Path("reports") / path.relative_to(ROOT / "reports")))
        for database in ("metabase_app", "reports"):
            dump = subprocess.run(
                ["docker", "compose", "--env-file", str(ENV), "-f", str(HERE / "compose.yaml"), "exec", "-T",
                 "postgres", "pg_dump", "-U", "report_admin", "--format=custom", database],
                capture_output=True, check=True)
            archive.writestr(database + ".dump", dump.stdout)
    print(target)


if __name__ == "__main__":
    main()
