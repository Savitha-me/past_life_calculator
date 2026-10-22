"""core/constants.py  (ADD these to your existing file)

All text comes from the astrologer's "Past Life's Karma" document.
"""

# Sign number (1=Aries ... 12=Pisces) -> ruling planet (classical lords:
# Scorpio = Mars, Aquarius = Saturn; Rahu/Ketu are not sign lords)
SIGN_LORDS = {
    1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon", 5: "Sun", 6: "Mercury",
    7: "Venus", 8: "Mars", 9: "Jupiter", 10: "Saturn", 11: "Saturn", 12: "Jupiter",
}

# House where the 5th lord sits -> karma area
_FIFTH_LORD_AREAS = {
    2: "money and family",
    3: "younger siblings",
    4: "mother, property and education",
    5: "children",
    6: "enemy, debt and illness",
    7: "spouse",
    8: "inheritance",
    9: "father and higher education",
    10: "career",
    11: "elder siblings",
    # ASSUMPTION: the document says "12th house Lord in the 12th house".
    # Treated as "5th house Lord in the 12th house". Confirm with the astrologer.
    12: "foreign and sleep comforts",
}

FIFTH_LORD_KARMA = {
    1: {
        "area": "Effortless benefits",
        "statement": "The native will get all the benefits effortlessly.",
    },
    **{
        house: {
            "area": area.capitalize(),
            "statement": f"The native will experience karma related to {area}.",
        }
        for house, area in _FIFTH_LORD_AREAS.items()
    },
}

# Planet sitting in the 5th house -> karma area
_PLANET_IN_FIFTH_AREAS = {
    "Sun": "father",
    "Moon": "mother",
    "Mars": "siblings",
    "Mercury": "maternal uncle",
    "Jupiter": "children",
    "Venus": "spouse",
    "Saturn": "job, labor, service and servant",
    "Rahu": "worldly pleasures",
    "Ketu": "spirituality",
}

PLANET_IN_FIFTH_KARMA = {
    planet: {
        "area": area.capitalize(),
        "statement": f"The native will experience karma related to {area}.",
    }
    for planet, area in _PLANET_IN_FIFTH_AREAS.items()
}