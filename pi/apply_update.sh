#!/usr/bin/env bash
# Applies a pending update triggered by the web UI writing data/update.flag.
# Activated by wled-scheduler-update.service, which runs as root — acceptable
# here specifically because this is a fixed, hardcoded sequence with no
# request-supplied input: git pull, reinstall deps, migrate, remove flag,
# restart. The unprivileged app process writes only the flag file; it never
# runs git, pip, or systemctl directly.
set -euo pipefail

INSTALL_DIR="/opt/wled-scheduler"
VENV_PYTHON="$INSTALL_DIR/venv/bin/python"

export INSTALL_DIR VENV_PYTHON

cd "$INSTALL_DIR"

echo "[update] Pulling latest code..."
git pull --ff-only

echo "[update] Reinstalling package..."
"$VENV_PYTHON" -m pip install -e . --quiet

echo "[update] Running migrations..."
"$INSTALL_DIR/pi/migrate.sh"

echo "[update] Removing update flag..."
rm -f data/update.flag

echo "[update] Restarting service..."
systemctl restart wled-scheduler

echo "[update] Done."
