"""rule_engine/karma_calculator.py

Combines the three rules:
  - planets in the 5th house  -> their karma
  - NO planet in the 5th house -> the 5th lord's karma (document's fallback)

Both results are always returned, so nothing is lost if the astrologer
wants the lord's karma shown even when planets are present.
"""
from rule_engine.fifth_house_logic import analyze_fifth_house
from rule_engine.fifth_lord_logic import analyze_fifth_lord
from rule_engine.planet_fifth_house import analyze_planets_in_fifth  # must match your file name

SOUL_MASTERED_TITLE = "What your soul already mastered"
FIFTH_HOUSE_LABEL = "5TH HOUSE — PAST-LIFE KARMA"
SOUL_DIRECTION_TITLE = "Your Soul's Direction"
SOUL_DIRECTION_LABEL = "5TH HOUSE — KARMA DIRECTION"
SPIRITUAL_GROWTH_TITLE = "Spiritual Growth"


def calculate_karma(chart: dict) -> dict:
    fifth_house = analyze_fifth_house(chart)
    fifth_lord = analyze_fifth_lord(chart, fifth_house)
    planets_in_fifth = analyze_planets_in_fifth(fifth_house)

    if planets_in_fifth:
        primary_source = "planet_in_fifth"
        primary_karma = [
            {"source": primary_source, **item} for item in planets_in_fifth
        ]
    else:
        primary_source = "fifth_lord"
        primary_karma = [{
            "source": primary_source,
            "planet": fifth_lord["planet"],
            "area": fifth_lord["area"],
            "statement": fifth_lord["statement"],
        }]

    return {
        "ascendant": chart["ascendant"],
        "fifth_house": fifth_house,
        "fifth_lord": fifth_lord,
        "planets_in_fifth": planets_in_fifth,
        "primary_source": primary_source,
        "primary_karma": primary_karma,
    }


def build_soul_mastered_header(chart: dict, analysis: dict) -> dict:
    """Label, badge and title for the "What your soul already mastered" card.

    Lead planet = the first planet of the primary karma (a planet in the 5th
    house, or the 5th lord when the 5th house is empty).
        label : "KETU — PAST-LIFE KARMA"
        badge : "<sign> · <nakshatra>" of that planet
    """
    planet = analysis["primary_karma"][0]["planet"]
    info = chart["planets"][planet]

    badge_parts = [info["sign"]]
    if info.get("nakshatra"):
        badge_parts.append(info["nakshatra"])

    return {
        "label": f"{planet.upper()} — PAST-LIFE KARMA",
        "badge": " · ".join(badge_parts),
        "title": SOUL_MASTERED_TITLE,
    }


def build_fifth_house_header(analysis: dict) -> dict:
    """Label, badge and title for the "Your 5th house falls in <sign>" card."""
    sign = analysis["fifth_house"]["sign"]
    return {
        "label": FIFTH_HOUSE_LABEL,
        "badge": sign,
        "title": f"Your 5th house falls in {sign}",
    }


def build_soul_direction_header() -> dict:
    """Label and title for the "Your Soul's Direction" card."""
    return {
        "label": SOUL_DIRECTION_LABEL,
        "title": SOUL_DIRECTION_TITLE,
    }


def build_spiritual_growth_header() -> dict:
    """Title for the "Spiritual Growth" card."""
    return {"title": SPIRITUAL_GROWTH_TITLE}