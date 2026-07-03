"""Centralized environment-driven configuration.

One obvious home for every setting that comes from the environment,
rather than scattered os.environ.get calls in whichever module happens
to need one first. DATABASE_PATH used to live directly in
app.database; it's consolidated here now that the scheduler loop needs
its own env-driven setting (the poll interval) too.
"""

import os
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

# Set once, the first time this module is imported, which for a real
# deployment is effectively process start (app.main imports app.config
# at module load, before uvicorn starts accepting connections). Used to
# compute uptime on request rather than storing it, so it stays correct
# without a background ticker. A `--reload` code change spawns a new
# process, so this correctly resets to that restart's time, not the
# original one.
START_TIME = datetime.now(UTC)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/scheduler.db")
SCHEDULER_POLL_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_POLL_INTERVAL_SECONDS", "30"))

# mDNS device tracking (app.mdns), replacing the old HTTP polling health
# check entirely. WLED's own A/SRV records carry a 120s TTL; the sweep
# interval only needs to be comfortably under that so 2 missed cycles
# lands in the 2-4 minute range documented in app/mdns.py, not tied to
# the TTL value itself (which isn't configurable, it's WLED's).
MDNS_SWEEP_INTERVAL_SECONDS = int(os.environ.get("MDNS_SWEEP_INTERVAL_SECONDS", "60"))
MDNS_OFFLINE_MISS_THRESHOLD = int(os.environ.get("MDNS_OFFLINE_MISS_THRESHOLD", "2"))
# Set to "false" to disable the persistent mDNS listener outright (used
# by the test suite, which otherwise pays for real multicast socket
# setup/teardown on every test that spins up the full app).
MDNS_ENABLED = os.environ.get("MDNS_ENABLED", "true").lower() not in ("false", "0", "")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Controls whether the /api/update/apply endpoint can trigger an in-place
# update. Defaults to "manual" (correct for Docker and all generic deploys —
# a container cannot safely self-update without mounting the Docker socket).
# The Pi native install sets this to "systemd-flag", enabling the path-unit
# mechanism where the app writes a flag file and a root-level oneshot service
# applies the update outside the unprivileged app process.
UPDATE_MECHANISM = os.environ.get("UPDATE_MECHANISM", "manual")

# Read from the installed package's own metadata (works for both a
# regular and an editable install, confirmed) rather than hardcoding a
# second copy of the version string that could drift from pyproject.toml.
try:
    APP_VERSION = _pkg_version("wled-scheduler")
except PackageNotFoundError:
    APP_VERSION = "dev"
