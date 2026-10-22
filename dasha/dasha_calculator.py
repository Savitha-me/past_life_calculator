"""dasha/dasha_calculator.py

Entry point used by services/past_life_services.py.

    chart (Moon longitude) -> build tree -> find active periods -> card data
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dasha.dasha_periods import get_active_periods
from dasha.vimshottari import build_dasha_tree
from schemas.request import BirthDetailsRequest


def calculate_dasha(
    moon_longitude: float,
    birth: BirthDetailsRequest,
    now: Optional[datetime] = None,
) -> dict:
    """
    moon_longitude : absolute sidereal degrees, 0-360 (must match the chart's ayanamsa)
    birth          : the user's birth details
    now            : optional "as of" date (timezone-aware). Defaults to the current
                     time in the birth timezone.
    """
    if not 0 <= moon_longitude < 360:
        raise ValueError(
            f"moon_longitude must be absolute degrees between 0 and 360, got {moon_longitude}"
        )

    try:
        tz = ZoneInfo(birth.timezone)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Unknown timezone '{birth.timezone}'. "
            "On Windows, make sure the 'tzdata' package is installed."
        )

    birth_local = datetime.fromisoformat(birth.date_of_birth).replace(tzinfo=tz)
    now = now.astimezone(tz) if now else datetime.now(tz)

    tree = build_dasha_tree(moon_longitude, birth_local)

    return {
        "current_dasha": get_active_periods(tree, now),
        "full_tree": tree,
    }