import asyncio
import logging
import random
from typing import Awaitable, Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)
T=TypeVar("T")

#HTTP status codes for temporary problems and wait for few seconds and try again
RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}

def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Retry-After header ('5') -> 5.0 seconds."""
    if value and value.strip().isdigit():
        return float(value.strip())
    return None

def backoff_delay(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    retry_after: Optional[float] = None,
) -> float:
    delay = base_delay * (2 ** (attempt-1)) + random.uniform(0, base_delay)
    if retry_after:
        delay = max(delay, retry_after)
    return min(delay, max_delay)

async def retry_async(
        operation: Callable[[], Awaitable[T]],
        *,
        name: str,
        attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        retry_on: Tuple[Type[BaseException], ...] = (Exception,),
) -> T:
    """Runs 'await operation()'. If it raises one of 'retry_on', waits and tries again, upto
    how many times we are saying the model to complete its retry process."""
    attempts = max(1, attempts + 1)

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except retry_on as exc:
            if attempt >= attempts:
                logger.error("%s failed after %d attempt(s): %s", name, attempts, exc)
                raise
            delay = backoff_delay(attempt, base_delay, max_delay, getattr(exc, "retry_after", None))
            logger.warning(
                "%s failed (Attempt %d/%d): %s. Retrying in %.1f seconds",
                name, attempt, attempts, exc, delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("unreachable")    