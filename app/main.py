"""FastAPI app entrypoint.

Wires up the JSON API routers, the page routes, the startup bootstrap,
and the two background loops (the scheduler and device health check).
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, device_health, scheduler
from app.database import SessionLocal, ensure_default_settings
from app.routers import actions, devices, history, pages, schedules, settings

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WLED Scheduler v%s", config.APP_VERSION)

    # Alembic migrations (`alembic upgrade head`) are expected to have
    # already run by this point, typically as a Docker entrypoint step
    # before uvicorn starts.
    with SessionLocal() as db:
        ensure_default_settings(db)

    task = asyncio.create_task(scheduler.run_forever())
    health_task = asyncio.create_task(device_health.run_forever())
    yield
    task.cancel()
    health_task.cancel()
    for t in (task, health_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="WLED Scheduler", version=config.APP_VERSION, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(devices.router)
app.include_router(actions.router)
app.include_router(settings.router)
app.include_router(schedules.router)
app.include_router(history.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": config.APP_VERSION}
