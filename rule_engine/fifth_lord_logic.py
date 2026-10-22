"""rule_engine/fifth_lord_logic.py

Find the 5th house lord, see which house it sits in,
and return the karma for that house.
"""
from core.constants import FIFTH_LORD_KARMA, SIGN_LORDS


def analyze_fifth_lord(chart: dict, fifth_house: dict) -> dict:
    lord = SIGN_LORDS[fifth_house["sign_number"]]
    placement = chart["planets"][lord]
    house = placement["house"]
    karma = FIFTH_LORD_KARMA[house]

    return {
        "planet": lord,
        "sign": placement["sign"],
        "house": house,
        "area": karma["area"],
        "statement": karma["statement"],
    }