"""Database engine, session management, and startup bootstrap logic.

Schema creation itself is handled by Alembic migrations (``alembic
upgrade head``), run before the app starts. This module is only
responsible for the runtime engine/session setup and for seeding data
that every fresh install needs: the single Settings row.
"""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.models import Settings

# SQLite will not create its own containing directory. Without this,
# a fresh install with DATABASE_PATH=data/scheduler.db and no data/
# directory yet would fail on the very first connection.
db_dir = Path(config.DATABASE_PATH).parent
if str(db_dir) not in ("", "."):
    db_dir.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{config.DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Runs on every new connection, not just the first. SQLite forgets
    these settings per connection, so they have to be re-applied here
    rather than run once at startup."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency. Yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_default_settings(db: Session) -> Settings:
    """Idempotently make sure the singleton Settings row (id=1) exists.

    Safe to call on every startup, every time. Never overwrites an
    existing row, so it can't clobber latitude, longitude, timezone,
    or catch_up_missed once someone has actually configured them.
    Defaults to an unconfigured state: no location set, catch up off.
    """
    settings = db.get(Settings, 1)
    if settings is not None:
        return settings

    settings = Settings(id=1)
    db.add(settings)
    try:
        db.commit()
    except IntegrityError:
        # Another process won the race and inserted id=1 first.
        # Not expected in this single-process architecture, but cheap
        # to guard against. Roll back and read back whatever exists.
        db.rollback()
        settings = db.get(Settings, 1)
    return settings
