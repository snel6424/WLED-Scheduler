# Raspberry Pi Installation Guide

This guide walks through installing WLED Scheduler natively on a **Raspberry Pi Zero 2 W** running **Raspberry Pi OS Lite (64-bit)**. No Docker required.

> **Only the Raspberry Pi Zero 2 W is officially supported** for this install path. Other Pi boards may work but aren't tested.

---

## What you'll need

- A Raspberry Pi Zero 2 W
- A microSD card (8 GB or larger)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/) installed on your computer
- Your home WiFi network name and password

---

## Step 1 — Write the SD card

1. Open **Raspberry Pi Imager**.
2. Click **Choose Device** and select **Raspberry Pi Zero 2 W**.
3. Click **Choose OS**, scroll to **Raspberry Pi OS (other)**, and select **Raspberry Pi OS Lite (64-bit)**. Make sure it says 64-bit specifically.
4. Click **Choose Storage** and select your SD card.
5. Click **Next**. When asked "Would you like to apply OS customisation settings?", click **Edit Settings**.

In the settings panel, fill in:

- **Hostname** — something memorable, like `wled-scheduler` (you'll use this to reach the app). Whatever you choose, the app will be at `http://<hostname>.local:8000`.
- **Username and password** — set a username and password you'll use to SSH in.
- **Configure wireless LAN** — enter your WiFi network name (SSID) and password.
- Under **Services**, enable **SSH** and choose "Use password authentication".

Click **Save**, then **Yes** to apply settings, then **Yes** again to confirm writing the card.

6. Wait for the write to complete, then eject the card and insert it into your Pi.

---

## Step 2 — Boot the Pi

Plug in power and wait about **60 seconds** for the Pi to boot and connect to your WiFi network. You don't need to connect a monitor.

---

## Step 3 — SSH in

From your computer, open a terminal and run:

```bash
ssh <your-username>@<your-hostname>.local
```

For example, if you set the hostname to `wled-scheduler` and username to `pi`:

```bash
ssh pi@wled-scheduler.local
```

If the connection is refused, wait another 30 seconds and try again — the Pi may still be finishing its first-boot setup.

---

## Step 4 — Run the installer

Once connected via SSH, paste this single command and press Enter:

```bash
wget -qO- https://raw.githubusercontent.com/snel6424/WLED-Scheduler/main/pi/install.sh | sudo bash
```

The installer will:

- Install Python and other required packages
- Disable WiFi power-save mode (prevents the Pi from becoming intermittently unreachable)
- Download WLED Scheduler and set it up
- Configure it to start automatically on boot

It takes a few minutes. When it finishes, you'll see a message with the URL.

---

## Step 5 — Open the app

On any device on the same WiFi network, open a browser and go to:

```
http://<your-hostname>.local:8000
```

For example: `http://wled-scheduler.local:8000`

From there, go to **Settings** to enter your location and timezone, then **Devices** to add your first WLED light.

---

## Updating

From the app's **Settings** page, click **Check** under "Updates". If a new version is available, click **Update now** and confirm. The app will be briefly unavailable (about a minute) while it updates.

---

## Restoring from a backup

WLED Scheduler automatically backs up the database before any migration runs. If something goes wrong after an update, you can restore to an earlier state:

1. SSH into your Pi.
2. Run:

```bash
sudo /opt/wled-scheduler/pi/restore.sh
```

The script will list available backups by date and time (newest first). Enter the number of the backup you want, type `yes` to confirm, and the app will be restored and restarted automatically.

**When to use this:** if the app misbehaves after an update — schedules missing, settings gone, anything that looks like a database problem. Don't wait; restore immediately and then report the issue.

---

## Useful commands

Check whether the service is running:
```bash
sudo systemctl status wled-scheduler
```

View live logs:
```bash
sudo journalctl -u wled-scheduler -f
```

Restart the service manually:
```bash
sudo systemctl restart wled-scheduler
```
