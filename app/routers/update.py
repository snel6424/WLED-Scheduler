"""Update checker and one-click updater endpoints.

GET /api/update/check  — compares installed version against GitHub tags.
POST /api/update/apply — writes the update flag file (Pi installs only).

UPDATE_MECHANISM in config controls whether automatic apply is possible:
  "manual"        — check-only; apply is blocked. Correct for all Docker
                    and generic deploys (a container cannot safely self-update
                    without mounting the Docker socket, which is effectively
                    root on the host).
  "systemd-flag"  — Pi native install. Apply writes a flag file that the
                    wled-scheduler-update.path unit detects and hands off to a
                    root-level oneshot service, keeping git/pip/systemctl out
                    of the unprivileged app process.
"""

import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from app import config

router = APIRouter(prefix="/api/update", tags=["update"])

_GITHUB_TAGS_URL = "https://api.github.com/repos/snel6424/WLED-Scheduler/tags"
_FLAG_FILE = Path(config.DATABASE_PATH).parent / "update.flag"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _parse_version(tag: str) -> tuple[int, ...] | None:
    """Return a numeric tuple for a version tag, or None if it doesn't match."""
    m = _VERSION_RE.match(tag.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


@router.get("/check")
def check_for_update() -> dict:
    """Check GitHub tags for a newer version. Fails silently on any error."""
    current = config.APP_VERSION
    can_apply = config.UPDATE_MECHANISM == "systemd-flag"
    current_tuple = _parse_version(current)

    try:
        resp = httpx.get(
            _GITHUB_TAGS_URL,
            timeout=8.0,
            headers={"Accept": "application/vnd.github.v3+json"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        tags = resp.json()
    except Exception:
        return {
            "current_version": current,
            "latest_version": None,
            "update_available": False,
            "can_apply_automatically": can_apply,
        }

    # Filter to well-formed version tags and sort numerically so that
    # 0.10.0 correctly sorts after 0.9.0 (string sort would get this wrong).
    candidates: list[tuple[tuple[int, ...], str]] = []
    for tag in tags:
        name = tag.get("name", "")
        parsed = _parse_version(name)
        if parsed:
            candidates.append((parsed, name.lstrip("v")))

    if not candidates:
        return {
            "current_version": current,
            "latest_version": None,
            "update_available": False,
            "can_apply_automatically": can_apply,
        }

    candidates.sort(key=lambda x: x[0], reverse=True)
    latest_tuple, latest = candidates[0]

    update_available = current_tuple is not None and latest_tuple > current_tuple

    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": update_available,
        "can_apply_automatically": can_apply,
    }


@router.post("/apply")
def apply_update() -> dict:
    """Write the update flag file. Only available on Pi native installs."""
    if config.UPDATE_MECHANISM != "systemd-flag":
        raise HTTPException(
            status_code=400,
            detail=(
                "Automatic update is not available for this install type. "
                "To update, run: git pull && docker compose up --build -d"
            ),
        )
    try:
        _FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _FLAG_FILE.touch()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write update flag: {exc}")

    return {"status": "update_triggered"}
