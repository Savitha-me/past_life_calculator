"""ai/content_generator.py

1) generate_karma_content          -> "content" for each planet in the 5th house
2) generate_soul_mastered_content  -> two lines for "What your soul already mastered"
3) generate_fifth_house_content    -> two lines for "Your 5th house falls in <sign>"
4) generate_soul_direction_content -> one line for "Your Soul's Direction"
5) generate_spiritual_growth_content -> two lines for "Spiritual Growth"

The LLM only WRITES; every astrology fact comes from the rule engine.
If the LLM fails, the astrologer's own statements are used instead.
"""
import asyncio
import logging
import re

from ai.llm_client import generate_text
from ai.prompt_loader import load_prompt
from core.exceptions import LLMError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "common/system_prompt.txt"
PLANET_IN_FIFTH_PROMPT = "past_life/planet_in_fifth.txt"
SOUL_MASTERED_PROMPT = "past_life/soul_mastered.txt"
FIFTH_LORD_PROMPT = "past_life/fifth_lord_karma.txt"
SOUL_DIRECTION_PROMPT = "past_life/soul_direction.txt"
SPIRITUAL_GROWTH_PROMPT = "past_life/spiritual_growth.txt"
KARMA_SUMMARY_PROMPT = "past_life/fifth_house_karma.txt"


async def _write_sentence(prompt_file: str, **values) -> str:
    """Returns the LLM text, or "" if the LLM call fails."""
    system_prompt = load_prompt(SYSTEM_PROMPT)
    user_prompt = load_prompt(prompt_file, **values)
    try:
        return await generate_text(system_prompt, user_prompt)
    except LLMError as exc:
        logger.error("LLM failed for %s: %s", prompt_file, exc)
        return ""


def _join(items: list) -> str:
    """['a'] -> 'a' | ['a','b'] -> 'a and b' | ['a','b','c'] -> 'a, b and c'"""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------ planets in the 5th house
async def generate_karma_content(analysis: dict) -> dict:
    """Sets analysis["planets_in_fifth"][i]["content"] and returns analysis."""
    ascendant = analysis["ascendant"]["sign"]
    fifth_house_sign = analysis["fifth_house"]["sign"]
    planets = analysis["planets_in_fifth"]

    sentences = await asyncio.gather(*[
        _write_sentence(
            PLANET_IN_FIFTH_PROMPT,
            ascendant_sign=ascendant,
            fifth_house_sign=fifth_house_sign,
            planet=p["planet"],
            karma_area=p["area"],
            karma_statement=p["statement"],
        )
        for p in planets
    ])

    for planet, sentence in zip(planets, sentences):
        planet["content"] = f"{planet['statement']} {sentence}".strip()

    return analysis


# ------------------------------------- "What your soul already mastered"
def _describe_karma_source(analysis: dict) -> str:
    if analysis["primary_source"] == "planet_in_fifth":
        names = ", ".join(item["planet"] for item in analysis["primary_karma"])
        return f"{names} placed in the 5th house"

    lord = analysis["fifth_lord"]
    return (
        f"the 5th house lord {lord['planet']}, placed in house "
        f"{lord['house']} in {lord['sign']}"
    )


async def generate_soul_mastered_content(analysis: dict) -> str:
    """Two short sentences built from the primary karma of the 5th house."""
    items = analysis["primary_karma"]
    statements = " ".join(item["statement"] for item in items)

    text = await _write_sentence(
        SOUL_MASTERED_PROMPT,
        ascendant_sign=analysis["ascendant"]["sign"],
        fifth_house_sign=analysis["fifth_house"]["sign"],
        karma_source=_describe_karma_source(analysis),
        karma_areas=", ".join(item["area"].lower() for item in items),
        karma_statements=statements,
    )
    return text or statements  # fallback: the astrologer's own statements


# ----------------------------------- "Your 5th house falls in <sign>"
async def generate_fifth_house_content(analysis: dict) -> str:
    """Two short sentences about the 5th house and where its lord sits."""
    lord = analysis["fifth_lord"]

    text = await _write_sentence(
        FIFTH_LORD_PROMPT,
        ascendant_sign=analysis["ascendant"]["sign"],
        fifth_house_sign=analysis["fifth_house"]["sign"],
        fifth_lord=lord["planet"],
        lord_sign=lord["sign"],
        lord_house=lord["house"],
        karma_area=lord["area"].lower(),
        karma_statement=lord["statement"],
    )
    return text or lord["statement"]  # fallback: the astrologer's statement


# ------------------------------------------------ "Your Soul's Direction"
async def generate_soul_direction_content(analysis: dict) -> str:
    """One sentence: where this life asks the soul to grow (primary karma)."""
    items = analysis["primary_karma"]
    areas = _join([item["area"].lower() for item in items])
    planets = _join([item["planet"] for item in items])

    text = await _write_sentence(
        SOUL_DIRECTION_PROMPT,
        ascendant_sign=analysis["ascendant"]["sign"],
        fifth_house_sign=analysis["fifth_house"]["sign"],
        karma_source=_describe_karma_source(analysis),
        lead_planets=planets,
        karma_areas=areas,
    )
    # fallback: the same pattern, built from the rule engine's own data
    return text or (
        f"This life, your soul moves toward {areas} — "
        f"the growth your {planets} calls you into."
    )


# ------------------------------------------------------ "Spiritual Growth"
SPIRITUAL_GROWTH_FALLBACK = (
    "Deepen your connection with your inner self through reflection, "
    "mindfulness, and spiritual learning. Embrace practices that nurture "
    "inner peace, wisdom, and compassion."
)


async def generate_spiritual_growth_content(analysis: dict) -> str:
    """Two sentences of spiritual guidance based on the 5th house karma."""
    items = analysis["primary_karma"]

    text = await _write_sentence(
        SPIRITUAL_GROWTH_PROMPT,
        ascendant_sign=analysis["ascendant"]["sign"],
        fifth_house_sign=analysis["fifth_house"]["sign"],
        karma_source=_describe_karma_source(analysis),
        karma_areas=_join([item["area"].lower() for item in items]),
    )
    return _limit_sentences(text) if text else SPIRITUAL_GROWTH_FALLBACK


def _limit_sentences(text: str, max_sentences: int = 2) -> str:
    """Keeps only the first sentences, so the card never gets longer than asked."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences])


# ------------------------------------------------ 5th house karma (2 lines)
async def generate_karma_summary_content(analysis: dict) -> str:
    """ONE meaningful sentence written for this chart.
    If the LLM fails, the astrologer's statement is used instead."""
    items = analysis["primary_karma"]
    areas = _join([item["area"].lower() for item in items])
    statement = f"The native will experience karma related to {areas}."

    sentence = await _write_sentence(
        KARMA_SUMMARY_PROMPT,
        ascendant_sign=analysis["ascendant"]["sign"],
        fifth_house_sign=analysis["fifth_house"]["sign"],
        karma_source=_describe_karma_source(analysis),
        karma_areas=areas,
    )
    if sentence:
        return _limit_sentences(sentence, 1)
    return statement  # fallback when the LLM fails