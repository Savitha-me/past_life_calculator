"""api/routes/past_life.py

Every endpoint takes the SAME request body: BirthDetailsRequest.
Errors are handled globally in main.py.
"""
from fastapi import APIRouter, Query

from schemas.request import BirthDetailsRequest
from services.past_life_services import (
    generate_dasha_report,
    generate_fifth_house_report,
    generate_full_report,
    generate_karma_report,
    generate_past_life_report,
    generate_soul_direction_report,
    generate_soul_mastered_report,
    generate_spiritual_growth_report,
)

router = APIRouter(prefix="/past-life", tags=["Past Life"])


@router.post("/report")
async def get_full_report(
    birth: BirthDetailsRequest,
    refresh: bool = Query(False, include_in_schema=False),  # hidden from Swagger
):
    """Runs all parts at once. Returns the saved report if the same
    details were used before. Adding ?refresh=true by hand generates it again."""
    return await generate_full_report(birth, refresh)


@router.post("/chart")
async def get_chart(birth: BirthDetailsRequest):
    return await generate_past_life_report(birth)


@router.post("/dasha")
async def get_dasha(birth: BirthDetailsRequest, include_tree: bool = False):
    return await generate_dasha_report(birth, include_tree)


@router.post("/karma")
async def get_karma(birth: BirthDetailsRequest, details: bool = False):
    return await generate_karma_report(birth, details)


@router.post("/soul-mastery")
async def get_soul_mastery(birth: BirthDetailsRequest):
    return await generate_soul_mastered_report(birth)


@router.post("/fifth-house")
async def get_fifth_house(birth: BirthDetailsRequest):
    return await generate_fifth_house_report(birth)


@router.post("/soul-direction")
async def get_soul_direction(birth: BirthDetailsRequest):
    return await generate_soul_direction_report(birth)


@router.post("/spiritual-growth")
async def get_spiritual_growth(birth: BirthDetailsRequest):
    return await generate_spiritual_growth_report(birth)