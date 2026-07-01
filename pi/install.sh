#!/usr/bin/env bash
# One-time setup script for WLED Scheduler on Raspberry Pi OS Lite (64-bit).
#
# Run once via SSH after first boot:
#   wget -qO- https://raw.githubusercontent.com/snel6424/WLED-Scheduler/main/pi/install.sh | sudo bash
#
# Safe to re-run: updates an existing install (git pull, reinstall deps,
# restart) rather than failing if called a second time.
# Must be run as root (sudo).
set -euo pipefail

REPO_URL="https://github.com/snel6424/WLED-Scheduler.git"
INSTALL_DIR="/opt/wled-scheduler"
SERVICE_USER="wled-scheduler"

info()  { echo "[wled-scheduler] $*"; }
error() { echo "[wled-scheduler] ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || error "This script must be run as root (try: sudo bash install.sh)"

# --------------------------------------------------------------------------
# 1. System packages
# --------------------------------------------------------------------------
info "Updating package lists and installing dependencies..."
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip git avahi-daemon iw

# --------------------------------------------------------------------------
# 2. Disable WiFi power management (intermittent dropouts on Pi otherwise)
# --------------------------------------------------------------------------
info "Disabling WiFi power management..."

# Immediate effect for the current session.
iw dev wlan0 set power_save off 2>/dev/null || true

# Persistent via NetworkManager (default network manager on RPi OS Bookworm+).
NM_CONF="/etc/NetworkManager/conf.d/99-wifi-power-save.conf"
if [ ! -f "$NM_CONF" ]; then
    cat > "$NM_CONF" <<'EOF'
[connection]
wifi.powersave = 2
EOF
    # Reload NM config without dropping the connection.
    systemctl reload NetworkManager 2>/dev/null || true
fi

# --------------------------------------------------------------------------
# 3. Service account
# --------------------------------------------------------------------------
if ! id "$SERVICE_USER" &>/dev/null; then
    info "Creating service user '$SERVICE_USER'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# --------------------------------------------------------------------------
# 4. Clone or update the repository
# --------------------------------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Existing install found — pulling latest code..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# --------------------------------------------------------------------------
# 5. Python virtual environment and package install
# --------------------------------------------------------------------------
info "Setting up Python environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -e "$INSTALL_DIR" --quiet

# --------------------------------------------------------------------------
# 6. Data directory — writable by the service user, not the world
# --------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR/data/backups"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/data"
chmod 750 "$INSTALL_DIR/data"

# --------------------------------------------------------------------------
# 7. Database migrations (with pre-migration backup if needed)
# --------------------------------------------------------------------------
info "Running database migrations..."
export INSTALL_DIR VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
chmod +x "$INSTALL_DIR/pi/migrate.sh"
"$INSTALL_DIR/pi/migrate.sh"
# Migration ran as root here; re-set ownership so the service user can write.
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/data"

# --------------------------------------------------------------------------
# 8. Systemd services
# --------------------------------------------------------------------------
info "Installing systemd services..."
chmod +x \
    "$INSTALL_DIR/pi/run.sh" \
    "$INSTALL_DIR/pi/apply_update.sh"

cp "$INSTALL_DIR/pi/wled-scheduler.service"        /etc/systemd/system/
cp "$INSTALL_DIR/pi/wled-scheduler-update.path"    /etc/systemd/system/
cp "$INSTALL_DIR/pi/wled-scheduler-update.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now wled-scheduler
systemctl enable --now wled-scheduler-update.path

# --------------------------------------------------------------------------
# 9. Done
# --------------------------------------------------------------------------
HOSTNAME_VAL=$(hostname)
echo ""
echo "============================================================"
info "Setup complete!"
echo ""
echo "  Open WLED Scheduler at:  http://${HOSTNAME_VAL}.local:8000"
echo ""
echo "  Check service status:    sudo systemctl status wled-scheduler"
echo "  Follow logs:             sudo journalctl -u wled-scheduler -f"
echo "  Restore from backup:     sudo $INSTALL_DIR/pi/restore.sh"
echo "============================================================"
