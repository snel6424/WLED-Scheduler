#!/usr/bin/env bash
# Service entrypoint: run migrations (with pre-migration backup if needed),
# then start the application server.
# Executed by wled-scheduler.service as the wled-scheduler service user.
set -euo pipefail

INSTALL_DIR="/opt/wled-scheduler"
VENV_PYTHON="$INSTALL_DIR/venv/bin/python"

export INSTALL_DIR VENV_PYTHON

"$INSTALL_DIR/pi/migrate.sh"

exec "$VENV_PYTHON" -m uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}"
