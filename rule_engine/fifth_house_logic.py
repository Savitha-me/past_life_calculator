"""rule_engine/fifth_house_logic.py

The 5th house is counted from the Ascendant (whole sign).
Uses chart["houses"] built by charts/chart_builder.py.
"""
FIFTH_HOUSE = 5


def analyze_fifth_house(chart: dict) -> dict:
    house = chart["houses"][FIFTH_HOUSE]
    return {
        "house_number": FIFTH_HOUSE,
        "sign": house["sign"],
        "sign_number": house["sign_number"],
        "planets": list(house["planets"]),  # planets sitting in the 5th
    }