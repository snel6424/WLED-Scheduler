#!/usr/bin/env bash
# Restore the WLED Scheduler database from a backup.
#
# Run via SSH when you need to recover from a failed update or corrupt data:
#   sudo /opt/wled-scheduler/pi/restore.sh
#
# Lists available backups, asks you to confirm before touching anything, then
# swaps the database file and restarts the service.
# Must be run as root (sudo).
set -euo pipefail

INSTALL_DIR="/opt/wled-scheduler"
DB_PATH="$INSTALL_DIR/data/scheduler.db"
BACKUP_DIR="$INSTALL_DIR/data/backups"
SERVICE_USER="wled-scheduler"

[ "$(id -u)" -eq 0 ] || { echo "This script must be run as root (try: sudo $0)" >&2; exit 1; }

echo ""
echo "=== WLED Scheduler — Database Restore ==="
echo ""

# Collect backups newest-first.
mapfile -t BACKUPS < <(ls -t "$BACKUP_DIR"/scheduler_*.db 2>/dev/null || true)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "No backups found in $BACKUP_DIR."
    echo "Backups are created automatically before each database migration."
    exit 1
fi

echo "Available backups (newest first):"
for i in "${!BACKUPS[@]}"; do
    FNAME=$(basename "${BACKUPS[$i]}")
    # Parse timestamp from filename: scheduler_YYYYMMDD_HHMMSS.db
    TS="${FNAME#scheduler_}"
    TS="${TS%.db}"
    DATE_STR="${TS:0:4}-${TS:4:2}-${TS:6:2} ${TS:9:2}:${TS:11:2}:${TS:13:2}"
    printf "  %d. %s  (%s)\n" "$((i + 1))" "$DATE_STR" "$FNAME"
done

echo ""
read -rp "Enter backup number to restore (or q to cancel): " CHOICE

if [[ "$CHOICE" == "q" || "$CHOICE" == "Q" ]]; then
    echo "Cancelled."
    exit 0
fi

if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] \
    || [ "$CHOICE" -lt 1 ] \
    || [ "$CHOICE" -gt "${#BACKUPS[@]}" ]; then
    echo "Invalid selection." >&2
    exit 1
fi

SELECTED="${BACKUPS[$((CHOICE - 1))]}"
FNAME=$(basename "$SELECTED")

echo ""
echo "Selected: $FNAME"
echo ""
echo "This will replace the live database with that backup."
echo "The app will be stopped briefly while the restore runs."
echo ""
read -rp "Type 'yes' to confirm, anything else to cancel: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Stopping wled-scheduler service..."
systemctl stop wled-scheduler

echo "Restoring database..."
# Remove stale WAL/SHM sidecars so SQLite sees a clean, consistent database.
# Leaving a -wal from before the restore would cause SQLite to try to replay
# writes that no longer belong to this database file.
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"
cp "$SELECTED" "$DB_PATH"
chown "$SERVICE_USER:$SERVICE_USER" "$DB_PATH"

echo "Starting wled-scheduler service..."
systemctl start wled-scheduler

echo ""
echo "Restore complete. WLED Scheduler is back up using $FNAME."
