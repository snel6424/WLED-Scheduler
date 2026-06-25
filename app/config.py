"""Centralized environment-driven configuration.

One obvious home for every setting that comes from the environment,
rather than scattered os.environ.get calls in whichever module happens
to need one first. DATABASE_PATH used to live directly in
app.database; it's consolidated here now that the scheduler loop needs
its own env-driven setting (the poll interval) too.
"""

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/scheduler.db")
SCHEDULER_POLL_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_POLL_INTERVAL_SECONDS", "30"))
DEVICE_HEALTH_CHECK_INTERVAL_SECONDS = int(
    os.environ.get("DEVICE_HEALTH_CHECK_INTERVAL_SECONDS", "60")
)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Read from the installed package's own metadata (works for both a
# regular and an editable install, confirmed) rather than hardcoding a
# second copy of the version string that could drift from pyproject.toml.
try:
    APP_VERSION = _pkg_version("wled-scheduler")
except PackageNotFoundError:
    APP_VERSION = "dev"
