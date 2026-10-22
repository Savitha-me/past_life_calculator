"""charts/chart_builder.py

Calls the D1 API and converts its response into ONE internal format,
containing exactly what the rule engine (5th house karma logic) and the
dasha module need. If the external API changes, only this file changes.

Returned structure:
{
  "ascendant": {"sign": "Gemini", "sign_number": 3},
  "planets": {
      "Sun": {"sign": "Libra", "sign_number": 7, "house": 5,
              "longitude": 190.4, "api_house": 5},
      ... Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu
  },
  "houses": {
      1: {"sign": "Gemini", "sign_number": 3, "planets": []},
      ...
      5: {"sign": "Libra",  "sign_number": 7, "planets": ["Sun"]},
  },
  "moon_longitude": 215.3,      # absolute 0-360, used by the dasha
  "raw": {...}                  # original API response (debugging)
}

Houses are counted WHOLE SIGN from the ascendant, as the rules say
"5th house from the Ascendant".
"""
from __future__ import annotations

from typing import Any, Optional

from charts.d1_chart import d1_chart_client
from schemas.request import BirthDetailsRequest

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]


SANSKRIT_SIGNS = {
    "mesha": 1, "vrishabha": 2, "mithuna": 3, "karka": 4, "simha": 5,
    "kanya": 6, "tula": 7, "vrischika": 8, "dhanu": 9, "makara": 10,
    "kumbha": 11, "meena": 12,
}

REQUIRED_PLANETS = [
    "Sun", "Moon", "Mars", "Mercury", "Jupiter",
    "Venus", "Saturn", "Rahu", "Ketu",
]

PLANET_ALIASES = {
    "sun": "Sun", "moon": "Moon", "mars": "Mars", "mercury": "Mercury",
    "jupiter": "Jupiter", "venus": "Venus", "saturn": "Saturn",
    "rahu": "Rahu", "north node": "Rahu", "true node": "Rahu", "mean node": "Rahu",
    "ketu": "Ketu", "south node": "Ketu",
}

NAME_KEYS = ("name", "planet", "planet_name")
SIGN_KEYS = ("sign", "sign_name", "rashi", "rasi", "zodiac_sign")
SIGN_NUM_KEYS = ("sign_number", "sign_num", "sign_index", "rashi_number", "rasi_number")
ABS_LONGITUDE_KEYS = ("absolute_longitude", "sidereal_longitude", "abs_longitude")
LONGITUDE_KEYS = ("longitude",) + ABS_LONGITUDE_KEYS
HOUSE_KEYS = ("house", "house_number", "bhava")



def _nakshatra(longitude):
    """Absolute sidereal longitude (0-360) -> nakshatra name."""
    if longitude is None:
        return None
    return NAKSHATRAS[int(longitude / (360 / 27)) % 27]

# ---------------------------------------------------------------- helpers
def _first(entry: dict, keys: tuple) -> Any:
    for key in keys:
        if entry.get(key) is not None:
            return entry[key]
    return None


def _to_sign_number(value: Any) -> Optional[int]:
    """'Gemini' / 'Mithuna' / 'Gem' / 3 / '3' / {'name': 'Gemini'} -> 3 (1-12)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        return _to_sign_number(_first(value, ("name", "sign", "number", "index")))
    if isinstance(value, (int, float)):
        n = int(value)
        return n if 1 <= n <= 12 else None
    if isinstance(value, str):
        s = value.strip().lower()
        if s.isdigit():
            return _to_sign_number(int(s))
        if s in SANSKRIT_SIGNS:
            return SANSKRIT_SIGNS[s]
        if len(s) >= 3:
            for i, name in enumerate(SIGNS, start=1):
                if s[:3] == name.lower()[:3]:
                    return i
    return None


def _sign_of(entry: dict) -> Optional[int]:
    n = _to_sign_number(_first(entry, SIGN_KEYS))
    if n:
        return n
    n = _to_sign_number(_first(entry, SIGN_NUM_KEYS))
    if n:
        return n
    lon = _first(entry, ABS_LONGITUDE_KEYS)
    if lon is not None:
        return int((float(lon) % 360) // 30) + 1
    return None


def _absolute_longitude(entry: dict, sign_number: int) -> Optional[float]:
    """Return 0-360 longitude. If the API gives degrees WITHIN the sign (0-30),
    convert using the sign number."""
    lon = _first(entry, LONGITUDE_KEYS)
    if lon is None:
        return None
    lon = float(lon)
    start = (sign_number - 1) * 30
    if start <= lon % 360 < start + 30:
        return lon % 360
    return (start + lon) % 360


def _unwrap(raw: dict) -> dict:
    """Some APIs wrap the chart inside 'data' / 'result' / 'chart'."""
    if "planets" not in raw:
        for key in ("data", "result", "chart"):
            if isinstance(raw.get(key), dict):
                return raw[key]
    return raw


def _planet_entries(data: dict) -> list:
    planets = data.get("planets", [])
    if isinstance(planets, dict):  # {"Moon": {...}} shape
        return [{"name": k, **v} for k, v in planets.items() if isinstance(v, dict)]
    return [p for p in planets if isinstance(p, dict)]


def _extract_ascendant(data: dict, entries: list) -> int:
    asc = data.get("ascendant") or data.get("lagna") or data.get("ascendant_sign")
    n = _sign_of(asc) if isinstance(asc, dict) else _to_sign_number(asc)
    if n:
        return n

    # ascendant listed like a planet
    for p in entries:
        if str(_first(p, NAME_KEYS) or "").strip().lower() in ("ascendant", "lagna", "asc"):
            n = _sign_of(p)
            if n:
                return n

    # first house in the houses list
    houses = data.get("houses")
    if isinstance(houses, list):
        for h in houses:
            if isinstance(h, dict) and _first(h, HOUSE_KEYS) == 1:
                n = _sign_of(h)
                if n:
                    return n

    raise ValueError(
        f"Ascendant sign not found in D1 response. Top-level keys: {list(data.keys())}"
    )


# ------------------------------------------------------------------ main
async def build_chart(birth: BirthDetailsRequest) -> dict:
    raw = await d1_chart_client.get_d1_chart(birth)
    data = _unwrap(raw)
    entries = _planet_entries(data)

    asc_number = _extract_ascendant(data, entries)

    # ---- planets: sign + whole-sign house from the ascendant
    planets: dict = {}
    for p in entries:
        name = PLANET_ALIASES.get(str(_first(p, NAME_KEYS) or "").strip().lower())
        if name is None:
            continue  # ascendant, outer planets, etc.

        sign_number = _sign_of(p)
        if sign_number is None:
            raise ValueError(f"Sign not found for {name}. Its keys: {list(p.keys())}")

        longitude = _absolute_longitude(p, sign_number)

        planets[name] = {
            "sign": SIGNS[sign_number - 1],
            "sign_number": sign_number,
            "house": (sign_number - asc_number) % 12 + 1,
            "longitude": longitude,
            "nakshatra": _nakshatra(longitude),
            "api_house": _first(p, HOUSE_KEYS),
        }

    missing = [name for name in REQUIRED_PLANETS if name not in planets]
    if missing:
        raise ValueError(f"Planets missing from D1 response: {missing}")

    # ---- houses: sign of each house + planets sitting in it
    houses: dict = {}
    for h in range(1, 13):
        sign_number = (asc_number - 1 + h - 1) % 12 + 1
        houses[h] = {
            "sign": SIGNS[sign_number - 1],
            "sign_number": sign_number,
            "planets": [n for n in REQUIRED_PLANETS if planets[n]["house"] == h],
        }

    return {
        "ascendant": {"sign": SIGNS[asc_number - 1], "sign_number": asc_number},
        "planets": planets,
        "houses": houses,
        "moon_longitude": planets["Moon"]["longitude"],
        "raw": raw,
    }