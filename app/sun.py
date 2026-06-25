"""Sun event calculations, isolated behind a small interface so the
rest of the app doesn't need to know astral exists, and so this is the
one place that would need to change if the library ever did.

Inputs and outputs here are timezone-aware. The naive-UTC-everywhere
storage convention from app.models only applies once a concrete
instant has been computed; it isn't a property of this module.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun


class LocationNotConfigured(Exception):
    """Raised when a sunrise/sunset calculation is requested but
    latitude, longitude, or timezone haven't been set yet."""


def sun_times(
    latitude: float, longitude: float, tz_name: str, for_date: date
) -> dict[str, datetime]:
    """Returns {'sunrise': <tz-aware datetime>, 'sunset': <tz-aware datetime>}
    for the given date, in the given timezone."""
    location = LocationInfo(latitude=latitude, longitude=longitude, timezone=tz_name)
    events = sun(location.observer, date=for_date, tzinfo=ZoneInfo(tz_name))
    return {"sunrise": events["sunrise"], "sunset": events["sunset"]}
