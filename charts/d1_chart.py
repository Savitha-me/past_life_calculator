"""charts/d1_chart.py

Calls the QA Engine D1 chart API.

  - keeps the access token fresh (refresh token, cached in .token_cache.json)
  - retries temporary failures of BOTH the chart call and the token refresh call
    (network errors, timeouts, HTTP 408 / 429 / 500 / 502 / 503 / 504)
  - does NOT retry errors that would fail again (400, 404, 422 ...)
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings
from core.exceptions import AuthenticationError, ChartAPIError, TransientError
from schemas.request import BirthDetailsRequest
from utils.date_utils import to_datetime_local
from utils.retry import RETRY_STATUS_CODES, parse_retry_after, retry_async

logger = logging.getLogger(__name__)

TOKEN_CACHE_FILE = Path(".token_cache.json")  # add to .gitignore
REFRESH_MARGIN_SECONDS = 300  # refresh 5 minutes before expiry


def _attempts() -> int:
    return int(getattr(settings, "d1_max_attempts", 3))


def _base_delay() -> float:
    return float(getattr(settings, "d1_retry_base_delay", 0.5))


class D1ChartClient:
    """Calls the D1 chart API and keeps the access token fresh."""

    def __init__(self) -> None:
        self._access_token: str = settings.qa_access_token
        self._refresh_token: str = settings.qa_refresh_token
        self._expires_at: Optional[float] = None  # unknown until first refresh
        self._lock = asyncio.Lock()
        self._load_cached_tokens()

    # ---------- token storage ----------
    def _load_cached_tokens(self) -> None:
        """Newer tokens saved by a previous run win over the .env values."""
        if not TOKEN_CACHE_FILE.exists():
            return
        try:
            data = json.loads(TOKEN_CACHE_FILE.read_text())
            self._access_token = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._expires_at = data.get("expires_at")
        except (ValueError, KeyError):
            logger.warning("Ignoring unreadable token cache file")

    def _save_tokens(self) -> None:
        TOKEN_CACHE_FILE.write_text(
            json.dumps(
                {
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "expires_at": self._expires_at,
                }
            )
        )

    # ---------- refresh (with retry) ----------
    def _is_expiring(self) -> bool:
        if self._expires_at is None:
            return False  # unknown: rely on the 401 retry
        return time.time() >= self._expires_at - REFRESH_MARGIN_SECONDS

    async def _refresh_access_token(self, failed_token: str) -> None:
        async with self._lock:
            # Another request may have already refreshed while we waited
            if self._access_token != failed_token:
                return

            if not self._refresh_token:
                raise AuthenticationError("No refresh token available", 401)

            logger.info("Refreshing access token")
            refresh_url = f"{settings.qa_api_base_url}{settings.token_refresh_endpoint}"
            refresh_token = self._refresh_token

            async def attempt() -> httpx.Response:
                try:
                    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                        response = await client.post(refresh_url, json={"refresh_token": refresh_token})
                except httpx.RequestError as exc:
                    raise TransientError(f"Could not reach token refresh API: {exc!r}") from exc

                if response.status_code in RETRY_STATUS_CODES:
                    raise TransientError(
                        f"Token refresh failed with HTTP {response.status_code}",
                        response.status_code,
                        parse_retry_after(response.headers.get("Retry-After")),
                    )
                return response

            try:
                response = await retry_async(
                    attempt,
                    name="Token refresh",
                    attempts=_attempts(),
                    base_delay=_base_delay(),
                    retry_on=(TransientError,),
                )
            except TransientError as exc:
                raise ChartAPIError(str(exc), exc.status_code) from exc

            if response.status_code != 200:
                logger.error("Token refresh failed: %s %s", response.status_code, response.text)
                raise AuthenticationError(
                    "Token refresh failed. The refresh token may be invalid or expired.",
                    response.status_code,
                )

            data = response.json()
            self._access_token = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            ttl = data.get("expires_in", settings.access_token_ttl_seconds)
            self._expires_at = time.time() + ttl
            self._save_tokens()

    # ---------- request helpers ----------
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_payload(birth: BirthDetailsRequest) -> dict:
        return {
            "datetime_local": to_datetime_local(birth.date_of_birth),
            "timezone": birth.timezone,
            "latitude": birth.latitude,
            "longitude": birth.longitude,
            "altitude": birth.altitude,
            "location_name": birth.place_of_birth,
            "ayanamsa": birth.ayanamsa,
            "house_system": birth.house_system,
            "include_outer_planets": birth.include_outer_planets,
        }

    async def _post(self, client: httpx.AsyncClient, url: str, payload: dict) -> httpx.Response:
        """One request. An expired token (401) is refreshed once and re-sent;
        this does not use up a retry attempt."""
        used_token = self._access_token
        response = await client.post(url, json=payload, headers=self._headers())

        if response.status_code == 401:
            await self._refresh_access_token(used_token)
            response = await client.post(url, json=payload, headers=self._headers())

        return response

    # ---------- main call (with retry) ----------
    async def get_d1_chart(self, birth: BirthDetailsRequest) -> dict:
        url = f"{settings.qa_api_base_url}{settings.d1_chart_endpoint}"
        payload = self._build_payload(birth)

        # Refresh early if we know the token is about to expire
        if self._is_expiring():
            await self._refresh_access_token(self._access_token)

        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:

            async def attempt() -> dict:
                try:
                    response = await self._post(client, url, payload)
                except httpx.RequestError as exc:  # network problem or timeout
                    raise TransientError(f"Could not reach D1 chart API: {exc!r}") from exc

                status = response.status_code

                if status < 400:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise TransientError("D1 chart API returned invalid JSON", status) from exc

                if status in (401, 403):
                    raise AuthenticationError("D1 API rejected the token", status)

                if status in RETRY_STATUS_CODES:
                    raise TransientError(
                        f"D1 chart API failed with HTTP {status}: {response.text[:200]}",
                        status,
                        parse_retry_after(response.headers.get("Retry-After")),
                    )

                # 400, 404, 422 ... trying again would give the same answer
                logger.error("D1 API error: %s %s", status, response.text)
                raise ChartAPIError(f"D1 chart API failed: {response.text}", status)

            try:
                return await retry_async(
                    attempt,
                    name="D1 chart API",
                    attempts=_attempts(),
                    base_delay=_base_delay(),
                    retry_on=(TransientError,),
                )
            except TransientError as exc:
                raise ChartAPIError(str(exc), exc.status_code) from exc


d1_chart_client = D1ChartClient()