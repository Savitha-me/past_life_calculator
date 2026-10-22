from datetime import datetime
import swisseph as swe
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
NAKSHATRA_SANSKRIT = {
    1: "Ashwini",      2: "Bharani",        3: "Krittika",
    4: "Rohini",       5: "Mrigasira",      6: "Ardra",
    7: "Punarvasu",    8: "Pushya",         9: "Ashlesha",
    10: "Magha",       11: "PurvaPhalguni", 12: "UttaraPhalguni",
    13: "Hasta",       14: "Chitra",        15: "Swati",
    16: "Vishakha",    17: "Anuradha",      18: "Jyeshta",
    19: "Moola",       20: "Purvashada",    21: "Uttarashada",
    22: "Shravana",    23: "Dhanishta",     24: "Shatabhisha",
    25: "Purvabhadra", 26: "Uttarabhadra",  27: "Revati",
}

NAKSHATRA_LORD = {
    "Ashwini": "Ketu",      "Magha": "Ketu",           "Moola": "Ketu",
    "Bharani": "Venus",     "PurvaPhalguni": "Venus",   "Purvashada": "Venus",
    "Krittika": "Sun",      "UttaraPhalguni": "Sun",    "Uttarashada": "Sun",
    "Rohini": "Moon",       "Hasta": "Moon",            "Shravana": "Moon",
    "Mrigasira": "Mars",    "Chitra": "Mars",           "Dhanishta": "Mars",
    "Ardra": "Rahu",        "Swati": "Rahu",            "Shatabhisha": "Rahu",
    "Punarvasu": "Jupiter", "Vishakha": "Jupiter",      "Purvabhadra": "Jupiter",
    "Pushya": "Saturn",     "Anuradha": "Saturn",       "Uttarabhadra": "Saturn",
    "Ashlesha": "Mercury",  "Jyeshta": "Mercury",       "Revati": "Mercury",
}

ZODIAC = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SOUTH_INDIAN_LAYOUT = {
    "Pisces":      (0, 0),
    "Aries":       (0, 1),
    "Taurus":      (0, 2),
    "Gemini":      (0, 3),
    "Aquarius":    (1, 0),
    "Cancer":      (1, 3),
    "Capricorn":   (2, 0),
    "Leo":         (2, 3),
    "Sagittarius": (3, 0),
    "Scorpio":     (3, 1),
    "Libra":       (3, 2),
    "Virgo":       (3, 3),
}

SIGN_ABBREV = {
    "Aries": "Ari", "Taurus": "Tau", "Gemini": "Gem", "Cancer": "Can",
    "Leo": "Leo", "Virgo": "Vir", "Libra": "Lib", "Scorpio": "Sco",
    "Sagittarius": "Sag", "Capricorn": "Cap", "Aquarius": "Aqu", "Pisces": "Pis",
}

def get_sign_position(longitude):
    return ZODIAC[int(longitude // 30) % 12]
def longitude_to_dms(longitude):
    deg = int(longitude)
    mins_float = (longitude - deg) * 60

    mins = int(mins_float)
    secs = int((mins_float - mins) * 60)

    return f"{deg:02d}°{mins:02d}'{secs:02d}\""

def get_tithi(moon_lon, sun_lon):
    diff = (moon_lon - sun_lon) % 360
    tithi_num = int(diff // 12) + 1
    if tithi_num <= 15:
        paksha, tithi_day = "Waxing Moon", tithi_num
    else:
        paksha, tithi_day = "Waning Moon", tithi_num - 15
    suffix = "st" if tithi_day == 1 else "nd" if tithi_day == 2 else "rd" if tithi_day == 3 else "th"
    return f"{tithi_day}{suffix} {paksha}"


def get_nakshatra_from_longitude(longitude):
    span   = 360.0 / 27
    p_span = span / 4
    idx    = min(int(longitude / span), 26)
    pada   = min(int((longitude - idx * span) / p_span) + 1, 4)
    num    = idx + 1
    return num, NAKSHATRA_SANSKRIT.get(num, ""), pada


def build_rasi_chart(position_list):
    chart = {s: [] for s in ZODIAC}
    for p in position_list:
        lon  = float(p["LongitudeCalculations"]["LongitudeValue"])
        name = p.get("PlanetPlanetName", "")
        if name:
            chart[get_sign_position(lon)].append(name)
    return chart

def compute_planets(dt_utc, lat, lon):
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    SWE_PLANETS = {
        "Sun":     swe.SUN,
        "Moon":    swe.MOON,
        "Mars":    swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus":   swe.VENUS,
        "Saturn":  swe.SATURN,
        "Rahu":    swe.MEAN_NODE,
    }

    jd = swe.julday(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    )

    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    position_list = []

    for name, planet_id in SWE_PLANETS.items():
        result, _ = swe.calc_ut(jd, planet_id, flags)
        sid_lon   = result[0] % 360
        nak_num, nak_name, pada = get_nakshatra_from_longitude(sid_lon)
        position_list.append({
            "PlanetPlanetName": name,
            "LongitudeCalculations": {
                "LongitudeValue":     sid_lon,
                "nakshatraNumValue":  nak_num,
                "nakshatraPadaValue": pada,
            }
        })

    rahu_lon = next(
        float(p["LongitudeCalculations"]["LongitudeValue"])
        for p in position_list if p["PlanetPlanetName"] == "Rahu"
    )
    ketu_lon = (rahu_lon + 180) % 360
    kn, _, kp = get_nakshatra_from_longitude(ketu_lon)
    position_list.append({
        "PlanetPlanetName": "Ketu",
        "LongitudeCalculations": {
            "LongitudeValue":     ketu_lon,
            "nakshatraNumValue":  kn,
            "nakshatraPadaValue": kp,
        }
    })

    houses, ascmc = swe.houses(jd, lat, lon, b'W')
    asc_trop = ascmc[0]
    ayan     = swe.get_ayanamsa_ut(jd)
    asc_sid  = (asc_trop - ayan) % 360
    ln, _, lp = get_nakshatra_from_longitude(asc_sid)
    position_list.append({
        "PlanetPlanetName": "Lagna",
        "LongitudeCalculations": {
            "LongitudeValue":     asc_sid,
            "nakshatraNumValue":  ln,
            "nakshatraPadaValue": lp,
        }
    })

    return position_list, jd

def geocode_location(city, state, country):
    geocoder = Nominatim(user_agent="vedic_chart_generator_v2")
    query    = ", ".join(filter(None, [city, state, country]))
    loc      = geocoder.geocode(query, timeout=10)
    if not loc:
        raise ValueError(f"Could not geocode: {query}")
    lat, lon = loc.latitude, loc.longitude
    tz_str   = TimezoneFinder().timezone_at(lng=lon, lat=lat) or "UTC"
    return lat, lon, tz_str


def local_to_utc(year, month, day, hour, minute, second, tz_str):
    tz    = pytz.timezone(tz_str)
    local = tz.localize(datetime(year, month, day, hour, minute, second))
    return local.astimezone(pytz.utc).replace(tzinfo=None)

def assemble_chart(name, year, month, day, hour, minute, second,
                    latitude, longitude, timezone):
    dt_utc            = local_to_utc(year, month, day, hour, minute, second, timezone)
    position_list, jd = compute_planets(dt_utc, latitude, longitude)

    planet_positions = []

    lagna_sign = None

    for p in position_list:

        if p["PlanetPlanetName"] == "Lagna":

            lagna_lon = float(
                p["LongitudeCalculations"]["LongitudeValue"]
            )

            lagna_sign = get_sign_position(lagna_lon)

            break

    lagna_index = ZODIAC.index(lagna_sign)

    for p in position_list:

        planet_name = p["PlanetPlanetName"]

        longitude = float(
            p["LongitudeCalculations"]["LongitudeValue"]
        )

        sign = get_sign_position(longitude)

        sign_index = ZODIAC.index(sign)

        house = ((sign_index - lagna_index) % 12) + 1

        degree = longitude_to_dms(longitude % 30)

        planet_positions.append({
            "planet": planet_name,
            "sign": sign,
            "degree": degree,
            "house": house
        })

    lagna_lon = next(
        float(p["LongitudeCalculations"]["LongitudeValue"])
        for p in position_list if p["PlanetPlanetName"] == "Lagna"
    )
    moon_lon = next(
        float(p["LongitudeCalculations"]["LongitudeValue"])
        for p in position_list if p["PlanetPlanetName"] == "Moon"
    )
    sun_lon = next(
        float(p["LongitudeCalculations"]["LongitudeValue"])
        for p in position_list if p["PlanetPlanetName"] == "Sun"
    )

    nak_num, nak_name, _ = get_nakshatra_from_longitude(moon_lon)
    birth_day = datetime(year, month, day).strftime("%A")

    return {
    "name": name,

    "rasi_chart": build_rasi_chart(position_list),

    "planet_positions": planet_positions,

    "moon_longitude": moon_lon,

    "moon_nakshatra_num": nak_num,

    "moon_nakshatra_name": nak_name,

    "nakshatra_lord": NAKSHATRA_LORD.get(
        nak_name,
        ""
    ),

    "birth_datetime": datetime(
        year,
        month,
        day,
        hour,
        minute,
        second
    ),

    "julian_day": jd,
}

if __name__ == "__main__":
    result = assemble_chart(
        name="Test User",
        year=1975,
        month=6,
        day=29,
        hour=4,
        minute=7,
        second=0,
        latitude=10.9601,
        longitude=78.0766,
        timezone="Asia/Kolkata"
    )

    print(result)