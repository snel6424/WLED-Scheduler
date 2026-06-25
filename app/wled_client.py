"""Thin synchronous client for the WLED JSON API.

Calls to a given host are serialized through a per-host lock, never
parallel, per WLED's own guidance against firing concurrent requests
at one device. Callers (routers today, the scheduler loop later)
don't need to think about this; it's enforced here, once, regardless
of who's calling in.

The `tt` field, not `transition`, is used for transition_ms. WLED
treats `transition` as a persistent default and `tt` as a one-off
override for just this call, which is what an Action firing on a
schedule should do: not permanently change the device's default
transition time. Units are 100ms per step, so milliseconds are
divided by 100 and rounded.
"""

import threading
from typing import Any

import httpx

_DEFAULT_TIMEOUT = 5.0

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class WledClientError(Exception):
    """Raised for any failure talking to a WLED device: unreachable,
    timed out, connection refused, or a non-2xx response."""


def _lock_for(host: str) -> threading.Lock:
    with _locks_guard:
        if host not in _locks:
            _locks[host] = threading.Lock()
        return _locks[host]


def _request(
    method: str, host: str, path: str, json: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = f"http://{host}{path}"
    with _lock_for(host):
        try:
            response = httpx.request(method, url, json=json, timeout=_DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise WledClientError(f"{method} {url} failed: {exc}") from exc


def get_info(host: str) -> dict[str, Any]:
    return _request("GET", host, "/json/info")


def get_state(host: str) -> dict[str, Any]:
    return _request("GET", host, "/json/state")


def get_presets(host: str) -> list[dict[str, Any]]:
    """Normalizes WLED's /presets.json (an object keyed by preset id as
    a string, not a list) into [{id, name}, ...]. Preset 0 is reserved
    by WLED for "no preset" / the current live state and is skipped."""
    raw = _request("GET", host, "/presets.json")
    presets = []
    for key, value in raw.items():
        if key == "0" or not isinstance(value, dict):
            continue
        try:
            preset_id = int(key)
        except ValueError:
            continue
        name = value.get("n") or f"Preset {key}"
        presets.append({"id": preset_id, "name": name})
    return sorted(presets, key=lambda p: p["id"])


def post_state(
    host: str, payload: dict[str, Any], transition_ms: int | None = None
) -> dict[str, Any]:
    body = dict(payload)
    if transition_ms is not None:
        body["tt"] = round(transition_ms / 100)
    return _request("POST", host, "/json/state", json=body)
