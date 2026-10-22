"""rule_engine/planet_in_fifth_logic.py

Karma for every planet sitting in the 5th house.
"""
from core.constants import PLANET_IN_FIFTH_KARMA


def analyze_planets_in_fifth(fifth_house: dict) -> list:
    results = []
    for planet in fifth_house["planets"]:
        karma = PLANET_IN_FIFTH_KARMA.get(planet)
        if karma is None:
            continue
        results.append({
            "planet": planet,
            "area": karma["area"],
            "statement": karma["statement"],
        })
    return results