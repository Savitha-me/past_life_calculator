"""utils/date_utils.py"""
from datetime import datetime
from functools import lru_cache

from timezonefinder import TimezoneFinder


def to_datetime_local(value: str) -> str:
    """'2021-05-03T00:00:00' (or '2021-05-03 00:00') -> '2021-05-03T00:00:00'

    Gives the D1 API the exact format it expects.
    """
    return datetime.fromisoformat(value.strip()).isoformat(timespec="seconds")


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    # loaded once, on first use
    return TimezoneFinder()


def get_timezone_name(latitude: float, longitude: float) -> str:
    """5.5166667, 115.8666667 -> 'Asia/Kuching'"""
    name = _finder().timezone_at(lat=latitude, lng=longitude)
    if not name:
        raise ValueError(
            f"Could not find a timezone for latitude {latitude}, longitude {longitude}"
        )
    return name