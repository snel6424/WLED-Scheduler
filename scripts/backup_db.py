#!/usr/bin/env python3
"""Create a timestamped SQLite backup using the .backup() API.

Called from pi/migrate.sh before Alembic migrations when a migration is
pending. Also callable standalone: python scripts/backup_db.py

Uses sqlite3.Connection.backup() rather than a raw file copy, which handles
WAL-mode databases correctly — a raw cp can miss writes still in the -wal
sidecar file.

Keeps only the 3 most recent backups; older ones are removed automatically
so backups don't accumulate on constrained storage.
"""

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RETAIN = 3
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def main() -> None:
    db_path = Path(os.environ.get("DATABASE_PATH", "data/scheduler.db"))
    backup_dir = db_path.parent / "backups"

    if not db_path.exists():
        print(f"[backup] No database at {db_path}, skipping.", file=sys.stderr)
        sys.exit(0)

    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime(TIMESTAMP_FORMAT)
    dest = backup_dir / f"scheduler_{ts}.db"

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    print(f"[backup] Created: {dest}")

    # Enforce retention: keep only the RETAIN most recent backups.
    backups = sorted(backup_dir.glob("scheduler_*.db"), key=lambda p: p.name)
    for old in backups[:-RETAIN]:
        old.unlink()
        print(f"[backup] Removed old backup: {old.name}")


if __name__ == "__main__":
    main()
