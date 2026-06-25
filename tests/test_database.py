"""Tests for app.database.ensure_default_settings: must create exactly
one row, be a no-op on every later call, and never clobber a value
someone has already configured.
"""

from app.database import ensure_default_settings
from app.models import Settings


def test_first_call_creates_an_unconfigured_row(db):
    settings = ensure_default_settings(db)
    assert settings.id == 1
    assert settings.latitude is None
    assert settings.catch_up_missed is False


def test_second_call_is_a_noop_not_a_duplicate(db):
    ensure_default_settings(db)
    ensure_default_settings(db)
    assert db.query(Settings).count() == 1


def test_does_not_clobber_an_already_configured_value(db):
    ensure_default_settings(db)
    settings = db.get(Settings, 1)
    settings.latitude = 35.4676
    settings.longitude = -97.5164
    settings.timezone = "America/Chicago"
    db.commit()

    result = ensure_default_settings(db)
    assert result.latitude == 35.4676
    assert result.timezone == "America/Chicago"
