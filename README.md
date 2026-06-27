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

Requires [Docker](https://docs.docker.com/get-docker/).

```bash
git clone https://github.com/snel6424/WLED-Scheduler.git
cd WLED-Scheduler
docker compose up --build -d
```

Then open `http://<your device's IP address>:8000`.

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

## Roadmap

Designed, but not yet implemented:
- A one-command install path for Raspberry Pi, no Docker required,
  intended for non-technical users
- An in-app update checker and one-click updater

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), including the list of
features deliberately out of scope for now (device groups, playlists,
mDNS auto-discovery, manual live control, remote access) and why.

## License

MIT, see [LICENSE](LICENSE).
