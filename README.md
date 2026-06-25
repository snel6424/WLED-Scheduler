# WLED Scheduler

A self-hosted scheduler for [WLED](https://kno.wled.ge/) lights. Create
schedules that turn your lights on, off, or into a saved preset at a
fixed time or relative to sunrise/sunset, with no cloud dependency:
everything runs on your own network, talking directly to your WLED
devices over their local JSON API.

## Features (v1)

- Add WLED devices by IP address or hostname
- Schedules triggered by a fixed time, or by sunrise/sunset with an offset
- Actions: apply a saved device preset, or a custom on/off + brightness + color
- Day-of-week recurrence
- Run-now, to verify a schedule fires correctly before trusting it unattended
- Online/offline status for each device, checked periodically in the background
- Full run history, across all schedules or filtered to one device
- Catch-up behavior for schedules missed while the app was offline, configurable in Settings

Not in v1, by design: device groups, playlists, mDNS auto-discovery,
manual on-the-fly light control, remote access outside your LAN. See
`CONTRIBUTING.md` if you're interested in why, or in picking one of
these up.

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

Then open `http://localhost:8000`. Migrations run automatically before
the server starts. Data persists in `./data`, mounted as a volume.

### Without Docker

Requires Python 3.11+.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

Then open `http://localhost:8000`.

## Configuration

Every setting is an environment variable with a sensible default; see
`.env.example` for the full list (database path, background poll
intervals, log level, host/port).

Location (latitude, longitude, timezone) and the missed-schedule
catch-up behavior are configured in the app itself, under Settings,
not via environment variables, since they're things you set once
through the UI rather than at deploy time.

## Data and backups

Everything this app knows, devices, actions, schedules, and run
history, lives in one file: the SQLite database at `DATABASE_PATH`
(`data/scheduler.db` by default, or `./data/scheduler.db` on the host
when running via Docker Compose). There's no in-app export or backup
feature in v1. Back it up the same way you'd back up any file: copy
it somewhere while the app isn't actively writing to it, or stop the
container briefly first if you want to be extra safe.

## Development

```bash
pip install -e ".[dev]"
pytest                  # full suite
pytest -m "not slow"    # skip the one test that does real wall-clock sleeping
ruff check .            # lint
```

The test suite uses a small mock WLED server (`tests/mock_wled/`) so
the full suite, including device communication, runs without any
real hardware.

### Project layout

```
app/
  models.py, schemas.py      data layer and API contracts
  routers/                   JSON API and page routes
  scheduler.py                background loop: fires due schedules
  device_health.py            background loop: device reachability
  wled_client.py               talks to WLED's JSON API
  templates/, static/         server-rendered HTML, CSS, JS (no build step)
alembic/                      database migrations
tests/                        pytest suite, including the mock WLED server
```

### Database migrations

This project uses Alembic. After changing `app/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
```

Then **read the generated migration before applying it**. Autogenerate
reliably picks up new tables and columns, but not always things like
`CheckConstraint`s added to an existing column, those sometimes need
to be added by hand. When in doubt, generate it against a real
database and inspect the actual SQL it produces.

## License

MIT, see `LICENSE`.
