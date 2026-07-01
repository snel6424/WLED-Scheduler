# WLED Scheduler

**Automate your WLED lights, no cloud, no app, no subscription.**

WLED Scheduler is a self-hosted scheduler for WLED-powered lights.
Set them to turn on, off, or change to a saved preset at a fixed time
or relative to sunrise/sunset, and let it run unattended from there.
Everything happens on your own network, talking directly to your
lights, nothing is sent anywhere else.

- **Self-hosted**: runs on your own hardware, your data never leaves
  your network
- **No cloud dependency**: schedules, sunrise/sunset times, and
  device communication are all computed and handled locally
- **Lightweight**: a single SQLite database, no external services to
  run alongside it
- **Flexible scheduling**: fixed time, or sunrise/sunset with an
  offset, with day-of-week recurrence
- **Free and open source**: MIT licensed, nothing paywalled

---

## Installation

### Docker (recommended for most setups)

Requires [Docker](https://docs.docker.com/get-docker/).

```bash
git clone https://github.com/snel6424/WLED-Scheduler.git
cd WLED-Scheduler
docker compose up --build -d
```

Then open `http://<your device's IP address>:8000`.

> **Networking note:** device discovery and online/offline status use
> mDNS, which needs UDP multicast (224.0.0.251:5353). The provided
> `docker-compose.yml` runs the container with `network_mode: host` to
> allow that — Docker's default bridge network blocks multicast, so
> devices would otherwise always show as offline. `network_mode: host`
> is Linux-only; it's not supported the same way on Docker Desktop for
> Mac or Windows. If you're on one of those and can't use host
> networking, the [Raspberry Pi / native install](#raspberry-pi-no-docker)
> path avoids the issue entirely since there's no container network to
> work around.

### Raspberry Pi (no Docker)

If you're running on a **Raspberry Pi Zero 2 W** and want to skip Docker, a native install path is available. One SSH session, one command.

See [INSTALL_PI.md](INSTALL_PI.md) for the full guide.

---

## Getting started

Once it's running, two things to do before it can actually schedule
anything:

1. **Settings** → enter your latitude, longitude, and timezone. This
   is required before any sunrise/sunset-based schedule can be
   created.
2. **Devices** → add your WLED light by its IP address or hostname.

From there, head to **Schedules** to create your first one.

---

## Updating

```bash
git pull
docker compose up --build -d
```

---

## Features

### Scheduling
Create schedules triggered by a fixed time of day, or by sunrise or
sunset with a configurable offset (e.g., 15 minutes before sunset).
Each schedule can repeat on any combination of days of the week, and
can either apply a saved preset on the device or set a custom
on/off/brightness/color state.

### Devices
Add WLED lights by IP address or hostname and see live online/offline
status, checked automatically in the background.

### History
A full log of every schedule that's fired, filterable by device and
date range, showing what happened and whether it succeeded.

### Settings
Location and timezone configuration (used to calculate sunrise and
sunset), and missed-schedule catch-up behavior, controlling whether a
schedule missed while the app was offline fires late or is skipped.

---

### Screenshots
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/e3394739-e14c-4600-a775-3f047477fa59" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/f5a94062-ced4-494a-8045-86651c1e7b0d" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/b042bc04-959a-46ca-b842-d175e5bf95de" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/c0cf3ed2-c587-4e3b-9193-7bcd69dbea1c" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/83c4cbe0-3956-4781-ba95-7bf9fa552521" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/5b69c26b-cafb-4d26-bd3c-360863f4f425" />
<img width="341" height="555" alt="image" src="https://github.com/user-attachments/assets/44a38159-bcfd-4448-91c3-7765bc52a6f3" />

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), including the list of
features deliberately out of scope for now (device groups, playlists,
mDNS auto-discovery, manual live control, remote access) and why.

## License

MIT, see [LICENSE](LICENSE).
