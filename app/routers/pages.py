"""HTML page routes. Each one renders a near-empty template; the
actual data loads client-side via fetch calls to the JSON API that
already exists. No business logic belongs in this file.
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app import config

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "schedules.html", {"active_page": "schedules"})


@router.get("/devices")
def devices_page(request: Request):
    return templates.TemplateResponse(request, "devices.html", {"active_page": "devices"})


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
