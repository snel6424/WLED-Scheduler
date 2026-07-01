#!/usr/bin/env bash
# Check for pending Alembic migrations, snapshot the database if any exist,
# then apply them. Shared between pi/run.sh (called on every service start)
# and pi/apply_update.sh (called after pulling new code).
#
# Expects INSTALL_DIR and VENV_PYTHON to be set, or uses defaults.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/wled-scheduler}"
VENV_PYTHON="${VENV_PYTHON:-$INSTALL_DIR/venv/bin/python}"

cd "$INSTALL_DIR"

# Ask Alembic directly whether a migration is pending, rather than building
# separate detection logic. Compares the database's current revision against
# the set of heads the installed code defines.
MIGRATION_STATUS=$("$VENV_PYTHON" - <<'PYEOF'
import sys
sys.path.insert(0, ".")
from sqlalchemy import create_engine
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.database import DATABASE_URL

cfg = Config("alembic.ini")
script = ScriptDirectory.from_config(cfg)
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    ctx = MigrationContext.configure(conn)
    current = ctx.get_current_revision()
    heads = set(script.get_heads())
    print("pending" if current not in heads else "current")
PYEOF
)

if [ "$MIGRATION_STATUS" = "pending" ]; then
    echo "[migrate] Migration pending — creating database snapshot first..."
    "$VENV_PYTHON" scripts/backup_db.py
fi

"$VENV_PYTHON" -m alembic upgrade head
