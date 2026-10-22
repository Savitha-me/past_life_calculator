"""core/database.py

MongoDB connection (PyMongo's built-in async client).
Connects once when the app starts and closes when it stops.

If MongoDB is unreachable the app still runs; reports just are not saved.
"""
import logging
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure

from core.config import settings
from utils.retry import retry_async

logger = logging.getLogger(__name__)

_client: Optional[AsyncMongoClient] = None


async def connect_to_mongo() -> None:
    global _client
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)

    try:
        await retry_async(
        lambda: client.admin.command("ping"),  # checks the connection now
        name="MongoDB connection",
        attempts=int(getattr(settings, "mongo_max_attempts", 3)),
        base_delay=0.5,
        retry_on=(ConnectionFailure,),
        )
    except Exception as exc:
        logger.error("MongoDB not reachable, reports will NOT be saved: %s", exc)
        await client.close()
        _client = None
        return
    _client = client

    # one saved report per set of birth details
    try:
        await client[settings.mongodb_db_name]["reports"].create_index(
            "birth_key", unique=True
        )
    except Exception as exc:
        logger.warning("Could not create the birth_key index: %s", exc)

    logger.info("Connected to MongoDB database '%s'", settings.mongodb_db_name)


async def close_mongo_connection() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_database():
    """Returns the database, or None if MongoDB is not connected."""
    if _client is None:
        return None
    return _client[settings.mongodb_db_name]