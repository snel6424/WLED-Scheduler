"""HTML page routes and htmx fragment routes.

Page routes render full-page templates; fragment routes return partial
HTML for htmx swaps. No business logic lives here — pages call the
same DB queries that the JSON API already exposes, and fragments are
thin slices of the same data shaped for incremental DOM updates.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Device
from app.schemas import DeviceRead

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


def _device_reads(db: Session, sort: str = "name") -> list[DeviceRead]:
    """Fetch all devices and compute the derived `online` field via the
    schema. Sorting by status puts online devices first (then by name);
    everything else sorts by name only."""
    rows = list(db.execute(select(Device)).scalars())
    reads = [DeviceRead.model_validate(d) for d in rows]
    if sort == "status":
        reads.sort(key=lambda d: (not d.online, d.name.lower()))
    else:
        reads.sort(key=lambda d: d.name.lower())
    return reads


# ---------------------------------------------------------------------------
# Full-page routes
# ---------------------------------------------------------------------------


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "schedules.html", {"active_page": "schedules"})


@router.get("/devices")
def devices_page(request: Request, db: Session = Depends(get_db)):
    devices = _device_reads(db)
    return templates.TemplateResponse(
        request, "devices.html", {"active_page": "devices", "devices": devices}
    )


@router.get("/devices/{device_id}")
def device_detail_page(request: Request, device_id: str):
    return templates.TemplateResponse(
        request, "device_detail.html", {"active_page": "devices", "device_id": device_id}
    )


@router.get("/history")
def history_overview_page(request: Request):
    return templates.TemplateResponse(
        request, "history.html", {"active_page": "history", "schedule_id": None}
    )


@router.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(
        request, "settings.html", {"active_page": "settings", "app_version": config.APP_VERSION}
    )


@router.get("/schedules")
def schedules_page(request: Request):
    return templates.TemplateResponse(request, "schedules.html", {"active_page": "schedules"})


@router.get("/schedules/new")
def schedule_new_page(request: Request):
    return templates.TemplateResponse(
        request, "schedule_form.html", {"active_page": "schedules", "schedule_id": None}
    )


@router.get("/schedules/{schedule_id}/edit")
def schedule_edit_page(request: Request, schedule_id: str):
    return templates.TemplateResponse(
        request, "schedule_form.html", {"active_page": "schedules", "schedule_id": schedule_id}
    )


@router.get("/schedules/{schedule_id}/history")
def schedule_history_page(request: Request, schedule_id: str):
    return templates.TemplateResponse(
        request, "history.html", {"active_page": "schedules", "schedule_id": schedule_id}
    )


# ---------------------------------------------------------------------------
# htmx fragment routes
# ---------------------------------------------------------------------------


@router.get("/fragments/devices/list")
def devices_list_fragment(
    request: Request, sort: str = "name", db: Session = Depends(get_db)
):
    """Device rows only, for the sort-select hx-get swap. Includes
    OOB updates for stats and the systems card so one request keeps
    everything consistent."""
    devices = _device_reads(db, sort)
    return templates.TemplateResponse(
        request, "fragments/devices_list.html", {"devices": devices}
    )


@router.get("/fragments/devices/statuses")
def devices_statuses_fragment(request: Request, db: Session = Depends(get_db)):
    """Pure OOB payload — no main-swap content. Used by the 15-second
    hx-trigger polling element on the devices page to update badges,
    icons, and stats counters without touching the rest of the DOM."""
    devices = _device_reads(db)
    return templates.TemplateResponse(
        request, "fragments/devices_statuses.html", {"devices": devices}
    )
