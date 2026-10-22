"""services/past_life_services.py

Orchestrates the whole flow:
  Birth details -> D1 chart -> dasha -> 5th house rules -> AI content

Individual endpoints each run one part.
generate_full_report runs ALL parts from ONE chart fetch, and uses MongoDB:
  1. same details already saved  -> return the saved report
  2. not saved                   -> generate, save, return
"""
import asyncio

from ai.content_generator import (
    generate_fifth_house_content,
    generate_karma_summary_content,
    generate_soul_direction_content,
    generate_soul_mastered_content,
    generate_spiritual_growth_content,
)
from charts.chart_builder import build_chart
from dasha.dasha_calculator import calculate_dasha
from rule_engine.karma_calculator import (
    build_fifth_house_header,
    build_soul_direction_header,
    build_soul_mastered_header,
    build_spiritual_growth_header,
    calculate_karma,
)
from schemas.request import BirthDetailsRequest
from services.report_services import find_stored_report, save_report


# ------------------------------------------------------------ helpers
def _dasha_from_chart(chart: dict, birth: BirthDetailsRequest, include_tree: bool = False) -> dict:
    moon_longitude = chart.get("moon_longitude")
    if moon_longitude is None:
        raise ValueError("Moon longitude not found in the D1 chart response")

    result = calculate_dasha(moon_longitude, birth)

    response = {
        "moon_longitude": moon_longitude,
        "current_dasha": result["current_dasha"],
    }
    if include_tree:
        response["full_tree"] = result["full_tree"]
    return response


# ------------------------------------------------- single-part reports
async def generate_past_life_report(birth: BirthDetailsRequest) -> dict:
    return await build_chart(birth)


async def generate_dasha_report(birth: BirthDetailsRequest, include_tree: bool = False) -> dict:
    chart = await build_chart(birth)
    return _dasha_from_chart(chart, birth, include_tree)


async def generate_karma_report(birth: BirthDetailsRequest, details: bool = False) -> dict:
    chart = await build_chart(birth)
    analysis = calculate_karma(chart)

    content = await generate_karma_summary_content(analysis)
    if details:  # full rule-engine result, for debugging
        return {"content": content, "details": analysis}
    return {"content": content}


async def generate_soul_mastered_report(birth: BirthDetailsRequest) -> dict:
    chart = await build_chart(birth)
    analysis = calculate_karma(chart)

    header = build_soul_mastered_header(chart, analysis)
    content = await generate_soul_mastered_content(analysis)
    return {**header, "content": content}


async def generate_fifth_house_report(birth: BirthDetailsRequest) -> dict:
    chart = await build_chart(birth)
    analysis = calculate_karma(chart)

    header = build_fifth_house_header(analysis)
    content = await generate_fifth_house_content(analysis)
    return {**header, "content": content}


async def generate_soul_direction_report(birth: BirthDetailsRequest) -> dict:
    chart = await build_chart(birth)
    analysis = calculate_karma(chart)

    header = build_soul_direction_header()
    content = await generate_soul_direction_content(analysis)
    return {**header, "content": content}


async def generate_spiritual_growth_report(birth: BirthDetailsRequest) -> dict:
    chart = await build_chart(birth)
    analysis = calculate_karma(chart)

    header = build_spiritual_growth_header()
    content = await generate_spiritual_growth_content(analysis)
    return {**header, "content": content}


# ------------------------------------------------------- everything
async def generate_full_report(birth: BirthDetailsRequest, refresh: bool = False) -> dict:
    """All parts from ONE request body, with MongoDB storage.

    refresh=True skips the saved copy and generates a new report
    (the new one replaces the saved one).
    """
    # 1. same details already saved? -> return the saved report
    if not refresh:
        stored = await find_stored_report(birth)
        if stored is not None:
            return {**stored, "from_database": True}

    # 2. not saved -> generate (D1 API called once)
    chart = await build_chart(birth)

    dasha = _dasha_from_chart(chart, birth)       # deterministic
    analysis = calculate_karma(chart)             # deterministic

    # the five AI texts are written at the same time
    karma, mastered, fifth_house, direction, growth = await asyncio.gather(
        generate_karma_summary_content(analysis),
        generate_soul_mastered_content(analysis),
        generate_fifth_house_content(analysis),
        generate_soul_direction_content(analysis),
        generate_spiritual_growth_content(analysis),
    )

    report = {
        "chart": {key: value for key, value in chart.items() if key != "raw"},
        "dasha": dasha,
        "karma": {"content": karma},
        "soul_mastery": {
            **build_soul_mastered_header(chart, analysis),
            "content": mastered,
        },
        "fifth_house": {
            **build_fifth_house_header(analysis),
            "content": fifth_house,
        },
        "soul_direction": {
            **build_soul_direction_header(),
            "content": direction,
        },
        "spiritual_growth": {
            **build_spiritual_growth_header(),
            "content": growth,
        },
    }

    # 3. save it for next time
    await save_report(birth, report)

    return {**report, "from_database": False}