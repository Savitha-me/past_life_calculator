"""dasha/dasha_periods.py

Finds which periods are running on a given date, from the tree built
by dasha/vimshottari.py. Produces the data for the dasha card:

    Mahadasha | Antardasha | Pratyantar | Next Antardasha
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def format_month_year(iso: str) -> str:
    """'2025-10-14T08:00:00+05:30' -> 'Oct 2025'"""
    return _parse(iso).strftime("%b %Y")


def _find_index(periods: list, now: datetime) -> Optional[int]:
    """Index of the period where start <= now < end, else None."""
    for i, period in enumerate(periods):
        if _parse(period["StartDate"]) <= now < _parse(period["EndDate"]):
            return i
    return None


def _card(period: Optional[dict]) -> Optional[dict]:
    if period is None:
        return None
    return {
        "planet": period["Name"],
        "start": format_month_year(period["StartDate"]),
        "end": format_month_year(period["EndDate"]),
    }


def get_active_periods(tree: dict, now: datetime) -> dict:
    """Return the running Maha / Antar / Pratyantar and the next Antardasha.

    `now` must be timezone-aware, otherwise comparing with the tree fails.
    """
    empty = {
        "mahadasha": None,
        "antardasha": None,
        "pratyantar": None,
        "next_antardasha": None,
    }

    mahas = tree["BirthInformationDetailsWithDasaBhukti"]["PlanetaryCycleDetails"]

    m_idx = _find_index(mahas, now)
    if m_idx is None:
        return empty

    maha = mahas[m_idx]
    bhuktis = maha["Bhukti"]

    b_idx = _find_index(bhuktis, now)
    if b_idx is None:
        return empty

    bhukti = bhuktis[b_idx]
    a_idx = _find_index(bhukti["Antara"], now)
    antara = bhukti["Antara"][a_idx] if a_idx is not None else None

    # Next Antardasha: next one in this Mahadasha, or the first one of the next Mahadasha
    if b_idx + 1 < len(bhuktis):
        next_bhukti = bhuktis[b_idx + 1]
    elif m_idx + 1 < len(mahas):
        next_bhukti = mahas[m_idx + 1]["Bhukti"][0]
    else:
        next_bhukti = None

    return {
        "mahadasha": _card(maha),
        "antardasha": _card(bhukti),
        "pratyantar": _card(antara),
        "next_antardasha": _card(next_bhukti),
    }