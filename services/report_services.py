"""services/report_store.py

Saves generated reports in MongoDB and finds them again.

A saved report is matched on these six details:
    name, email, date of birth, place of birth, latitude, longitude
If all six are the same, the saved report is returned instead of
generating a new one.

Temporary connection problems are retried. A database problem never breaks
report generation: when it still fails, the error is only logged.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pymongo.errors import ConnectionFailure, PyMongoError

from core.config import settings
from core.database import get_database
from schemas.request import BirthDetailsRequest
from utils.retry import retry_async

logger = logging.getLogger(__name__)

COLLECTION = "past_life_calculator_reports"


def make_birth_key(birth: BirthDetailsRequest) -> str:
    """One key built from the six matching details.
    Text is trimmed and lower-cased so 'Daniel ' and 'daniel' match."""
    parts = [
        birth.name.strip().lower(),
        birth.email.strip().lower(),
        birth.date_of_birth,                         # already normalised by the model
        birth.place_of_birth.strip().lower(),
        f"{birth.latitude:.6f}",
        f"{birth.longitude:.6f}",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _local_time_text(moment_utc: datetime, timezone_name: str) -> str:
    """UTC moment -> wall-clock time in the given timezone, WITHOUT the offset,
    e.g. '2026-10-23T11:03:06'. The timezone name is saved in its own field."""
    try:
        local = moment_utc.astimezone(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        local = moment_utc  # unknown timezone: keep UTC
    return local.strftime("%Y-%m-%dT%H:%M:%S")


def _bson_safe(data: dict) -> dict:
    # MongoDB only allows text keys, but the chart has numbers as keys
    # (houses 1..12). A JSON round trip turns them into text.
    return json.loads(json.dumps(data))


async def find_stored_report(birth: BirthDetailsRequest) -> Optional[dict]:
    """Returns the saved report for these details, or None.
    Two attempts only: this runs while the user is waiting."""
    db = get_database()
    if db is None:
        return None

    key = make_birth_key(birth)
    try:
        doc = await retry_async(
            lambda: db[COLLECTION].find_one({"birth_key": key}, {"_id": 0, "report": 1}),
            name="MongoDB read",
            attempts=2,
            base_delay=0.2,
            retry_on=(ConnectionFailure,),
        )
    except PyMongoError as exc:
        logger.error("Could not read the saved report: %s", exc)
        return None

    return doc["report"] if doc else None


async def save_report(birth: BirthDetailsRequest, report: dict) -> None:
    """Saves the report. Same details again -> the old copy is replaced.
    Runs in the background, so more attempts are fine."""
    db = get_database()
    if db is None:
        return

    key = make_birth_key(birth)
    now_utc = datetime.now(timezone.utc)

    try:
        timezone_name = birth.timezone        # found from the request's latitude/longitude
    except ValueError:
        timezone_name = "UTC"

    document = {
        "birth_key": key,
        "birth_details": birth.model_dump(),
        "report": _bson_safe(report),
        "created_at": now_utc,                  # MongoDB always keeps dates in UTC
        "timezone": timezone_name,              # e.g. "America/New_York"
        "created_at_local": _local_time_text(now_utc, timezone_name),  # same moment, in that timezone
    }

    try:
        await retry_async(
            lambda: db[COLLECTION].replace_one({"birth_key": key}, document, upsert=True),
            name="MongoDB save",
            attempts=int(getattr(settings, "mongo_max_attempts", 3)),
            base_delay=0.5,
            retry_on=(ConnectionFailure,),
        )
    except PyMongoError as exc:
        logger.error("Could not save the report: %s", exc)