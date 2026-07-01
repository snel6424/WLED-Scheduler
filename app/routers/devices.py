"""Device endpoints. The only router that talks to wled_client, since
devices are the one resource backed by a real network call rather than
just the database.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, mdns, wled_client
from app.database import get_db
from app.mdns import strip_port
from app.models import Device
from app.schemas import DeviceCreate, DeviceRead, DeviceUpdate, PresetRead
from app.wled_client import WledClientError

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _capabilities_from_info(info: dict) -> dict:
    """Pulls just the handful of /json/info fields the rest of the app
    actually uses, rather than caching the entire (much larger) blob.

    wifi.signal is a 0-100 relative quality percentage, per WLED's own
    docs; there is no dBm/RSSI field in the documented API, so signal
    strength is shown as a percentage/qualitative label, not dBm.
    """
    leds = info.get("leds", {})
    wifi = info.get("wifi", {})
    return {
        "name": info.get("name"),
        "version": info.get("ver"),
        "led_count": leds.get("count"),
        "max_segments": leds.get("maxseg"),
        "fx_count": info.get("fxcount"),
        "palette_count": info.get("palcount"),
        "wifi_signal_percent": wifi.get("signal"),
    }


def _get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("", response_model=DeviceRead, status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)) -> Device:
    existing = db.execute(select(Device).where(Device.host == payload.host)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A device at {payload.host!r} already exists")

    try:
        info = wled_client.get_info(payload.host)
    except WledClientError as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not reach a WLED device at {payload.host!r}: {exc}"
        ) from exc

    name = payload.name if payload.name is not None else info.get("name")
    if not name:
        raise HTTPException(
            status_code=422,
            detail=(
                "Name is required when creating a device. "
                "Provide a device name or ensure the WLED device reports its own name."
            ),
        )

    device = Device(
        name=name,
        host=payload.host,
        room=payload.room,
        mac=info.get("mac"),
        mdns_name=payload.mdns_name,
        capabilities=_capabilities_from_info(info),
    )
    db.add(device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"A device at {payload.host!r} already exists"
        ) from exc
    db.refresh(device)
    return device


@router.get("", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    return list(db.execute(select(Device).order_by(Device.name)).scalars())


@router.get("/scan")
async def scan_devices(timeout: float = 5.0, db: Session = Depends(get_db)) -> list[dict]:
    """Bounded mDNS browse for the add-device flow. Returns devices
    advertising `_wled._tcp.local.` that aren't already in the device
    list (matched by mdns_name or by IP), so the UI only ever shows
    devices worth adding."""
    if not config.MDNS_ENABLED:
        raise HTTPException(status_code=503, detail="mDNS is disabled (MDNS_ENABLED=false)")

    timeout = max(0.5, min(timeout, 15.0))
    existing = list(db.execute(select(Device)).scalars())
    existing_mdns_names = {d.mdns_name for d in existing if d.mdns_name}
    existing_ips = {strip_port(d.host) for d in existing}

    results = await mdns.scan(timeout=timeout)
    return [
        r
        for r in results
        if r["mdns_name"] not in existing_mdns_names and r["host"] not in existing_ips
    ]


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: str, db: Session = Depends(get_db)) -> Device:
    return _get_device_or_404(db, device_id)


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(device_id: str, payload: DeviceUpdate, db: Session = Depends(get_db)) -> Device:
    device = _get_device_or_404(db, device_id)
    update_fields = payload.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


@router.post("/{device_id}/refresh", response_model=DeviceRead)
def refresh_device(device_id: str, db: Session = Depends(get_db)) -> Device:
    device = _get_device_or_404(db, device_id)
    try:
        info = wled_client.get_info(device.host)
    except WledClientError as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not reach {device.name!r} at {device.host!r}: {exc}"
        ) from exc

    device.mac = info.get("mac")
    device.capabilities = _capabilities_from_info(info)
    # A successful manual refresh is real, if incidental, proof of
    # reachability -- worth reflecting in online status immediately
    # rather than making the user wait for mDNS to notice. This is a
    # one-off, user-triggered HTTP call, not a reintroduction of the
    # periodic polling loop app.mdns replaced.
    mdns.mark_online(db, device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}/presets", response_model=list[PresetRead])
def get_device_presets(device_id: str, db: Session = Depends(get_db)) -> list[dict]:
    device = _get_device_or_404(db, device_id)
    try:
        return wled_client.get_presets(device.host)
    except WledClientError as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not reach {device.name!r} at {device.host!r}: {exc}"
        ) from exc


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str, db: Session = Depends(get_db)) -> None:
    device = _get_device_or_404(db, device_id)
    db.delete(device)
    db.commit()


class _ApplyBody(BaseModel):
    payload: dict[str, Any]


@router.post("/{device_id}/apply")
def apply_state(device_id: str, body: _ApplyBody, db: Session = Depends(get_db)) -> dict:
    device = _get_device_or_404(db, device_id)
    try:
        wled_client.post_state(device.host, body.payload)
        return {"status": "success"}
    except WledClientError as exc:
        return {"status": "error", "error_message": str(exc)}
