"""dasha/vimshottari.py

Pure Vimshottari calculation. No API calls, no project imports.

Input : Moon's absolute sidereal longitude (0-360) + timezone-aware birth datetime
Output: full tree  Mahadasha -> Bhukti (Antardasha) -> Antara (Pratyantar)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

NAKSHATRA_SPAN = 360.0 / 27
DAYS_PER_YEAR = 365.25

VIMSHOTTARI_SEQUENCE: List[str] = [
    "Ketu", "Venus", "Sun", "Moon", "Mars",
    "Rahu", "Jupiter", "Saturn", "Mercury",
]

VIMSHOTTARI_YEARS: Dict[str, int] = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

TOTAL_YEARS = sum(VIMSHOTTARI_YEARS.values())  # 120


def _seq_from(planet: str) -> List[str]:
    idx = VIMSHOTTARI_SEQUENCE.index(planet)
    return VIMSHOTTARI_SEQUENCE[idx:] + VIMSHOTTARI_SEQUENCE[:idx]


def _iso(dt: datetime) -> str:
    # e.g. 2025-10-14T08:00:00+05:30
    return dt.isoformat(timespec="seconds")


def _split(parent_planet: str, start: datetime, end: datetime) -> List[list]:
    """Split [start, end] into 9 sub-periods, in Vimshottari proportion.
    The sequence starts with the parent planet itself.
    Returns [[planet, start, end], ...]."""
    total_days = (end - start).total_seconds() / 86400
    result: List[list] = []
    cursor = start
    for planet in _seq_from(parent_planet):
        days = total_days * (VIMSHOTTARI_YEARS[planet] / TOTAL_YEARS)
        nxt = cursor + timedelta(days=days)
        result.append([planet, cursor, nxt])
        cursor = nxt
    result[-1][2] = end  # remove floating-point drift
    return result


def _build_bhukti(
    maha_planet: str,
    maha_full_start: datetime,
    maha_end: datetime,
    birth: datetime,
) -> List[dict]:
    """Build Bhukti + Antara over the FULL Mahadasha length, then cut off
    anything that ended before birth. This matters only for the first
    Mahadasha, which was already running when the person was born."""
    bhuktis: List[dict] = []

    for b_planet, b_full_start, b_end in _split(maha_planet, maha_full_start, maha_end):
        if b_end <= birth:
            continue  # finished before birth

        antaras: List[dict] = []
        for a_planet, a_full_start, a_end in _split(b_planet, b_full_start, b_end):
            if a_end <= birth:
                continue
            antaras.append({
                "StartDate": _iso(max(a_full_start, birth)),
                "EndDate": _iso(a_end),
                "Name": a_planet,
            })

        bhuktis.append({
            "StartDate": _iso(max(b_full_start, birth)),
            "EndDate": _iso(b_end),
            "Name": b_planet,
            "Antara": antaras,
        })

    return bhuktis


def build_dasha_tree(
    moon_longitude: float,
    birth_datetime_local: datetime,
    moon_sign_num: Optional[int] = None,
    sun_sign_num: Optional[int] = None,
    ascendant_num: Optional[int] = None,
    birth_star_num: Optional[int] = None,
    cycles: int = 1,
) -> dict:
    """Build the Vimshottari tree.

    moon_longitude       : absolute sidereal degrees, 0-360 (same ayanamsa as the chart)
    birth_datetime_local : timezone-aware datetime of birth
    cycles               : 1 cycle = 120 years
    """
    if birth_datetime_local.tzinfo is None:
        raise ValueError(
            "birth_datetime_local must be timezone-aware (carrying the "
            "birth's local UTC offset), not naive. Localize it first "
            "(e.g. via zoneinfo) before calling this function."
        )

    moon_longitude = moon_longitude % 360.0

    nak_index = int(moon_longitude / NAKSHATRA_SPAN) % 27
    deg_into_nakshatra = moon_longitude - (nak_index * NAKSHATRA_SPAN)
    fraction_elapsed = deg_into_nakshatra / NAKSHATRA_SPAN

    starting_lord = VIMSHOTTARI_SEQUENCE[nak_index % 9]
    sequence = _seq_from(starting_lord)

    maha_list: List[dict] = []
    cursor = birth_datetime_local

    for i, planet in enumerate(sequence * cycles):
        full_days = VIMSHOTTARI_YEARS[planet] * DAYS_PER_YEAR

        if i == 0:
            # Birth happened part-way through this Mahadasha
            full_start = birth_datetime_local - timedelta(days=fraction_elapsed * full_days)
            shown_start = birth_datetime_local
        else:
            full_start = cursor
            shown_start = cursor

        end = full_start + timedelta(days=full_days)

        maha_list.append({
            "StartDate": _iso(shown_start),
            "EndDate": _iso(end),
            "Name": planet,
            "Bhukti": _build_bhukti(planet, full_start, end, birth_datetime_local),
        })
        cursor = end

    return {
        "BirthInformationDetailsWithDasaBhukti": {
            "BirthInformations": {
                "MoonSign": moon_sign_num,
                "BirthStar": birth_star_num if birth_star_num is not None else nak_index + 1,
                "SunSign": sun_sign_num,
                "Ascendant": ascendant_num,
            },
            "PlanetaryCycleDetails": maha_list,
        }
    }