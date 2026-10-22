"""Access/refresh token handling for the external chart API.

Flow:
  get_access_token()
    -> cached access token still valid?  use it
    -> else try REFRESH token
    -> if refresh is rejected/missing, fall back to LOGIN with username/password
Concurrent requests share one lock, so only ONE refresh happens at a time.

ASSUMPTIONS (adjust to Swagger):
  login   : POST {login_path}   body {"username", "password"}
  refresh : POST {refresh_path} body {"refresh_token"}
  both return {"access_token", "refresh_token"?, "expires_in"?}
"""
import asyncio
import base64
import json
import logging
import os
import time

import httpx

from core.config import get_settings
from core.exceptions import ChartAuthError, ChartServiceError

logger = logging.getLogger(__name__)

DEFAULT_LIFETIME_SECONDS = 300  # used only if API gives no expiry info


def _pick(data: dict, *keys):
    for k in keys:
        if data.get(k):
            return data[k]
    return None


def _jwt_expiry(token: str) -> float | None:
    """Read 'exp' from a JWT without verifying it (we only need the timing)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:
        return None


class TokenManager:
    def __init__(self) -> None:
        s = get_settings()
        self._access: str | None = s.chart_api_access_token or None
        self._refresh: str | None = s.chart_api_refresh_token or None
        # Seeded access token: use its JWT expiry if readable, else assume it is already stale
        self._expires_at: float = (_jwt_expiry(self._access) or 0.0) if self._access else 0.0
        self._lock = asyncio.Lock()
        self._load_cache()

    # ---------- public ----------
    async def get_access_token(self, stale: str | None = None) -> str:
        """Return a valid access token.
        Pass `stale` (a token that just got a 401) to force renewal, but only if
        nobody else has already renewed it in the meantime."""
        async with self._lock:
            if self._access and not self._is_expired() and self._access != stale:
                return self._access
            await self._renew()
            return self._access  # type: ignore[return-value]

    # ---------- token file (survives restarts / refresh-token rotation) ----------
    def _load_cache(self) -> None:
        s = get_settings()
        if not s.chart_api_token_file:
            return
        try:
            with open(s.chart_api_token_file) as f:
                data = json.load(f)
        except (FileNotFoundError, ValueError, OSError):
            return
        # If you pasted NEW tokens in .env, the saved file is outdated -> ignore it
        if data.get("seed_refresh", "") != s.chart_api_refresh_token:
            logger.info("Token file ignored: .env refresh token changed")
            return
        if data.get("refresh"):
            self._access = data.get("access")
            self._refresh = data["refresh"]
            self._expires_at = float(data.get("expires_at", 0))
            logger.info("Loaded tokens from token file")

    def _save_cache(self) -> None:
        s = get_settings()
        if not s.chart_api_token_file:
            return
        tmp = s.chart_api_token_file + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump({"seed_refresh": s.chart_api_refresh_token, "access": self._access,
                           "refresh": self._refresh, "expires_at": self._expires_at}, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, s.chart_api_token_file)   # atomic: never a half-written file
        except OSError as exc:
            logger.warning("Could not save token file: %s", exc)

    # ---------- internals ----------
    def _is_expired(self) -> bool:
        skew = get_settings().chart_api_token_skew_seconds
        return time.time() >= self._expires_at - skew

    async def _renew(self) -> None:
        if self._refresh:
            try:
                data = await self._post(get_settings().chart_api_refresh_path,
                                        {"refresh_token": self._refresh})
                self._store(data)
                logger.info("Chart API token refreshed")
                return
            except ChartAuthError:
                logger.warning("Refresh token rejected, falling back to login")
                self._refresh = None

        s = get_settings()
        if not (s.chart_api_username and s.chart_api_password):
            raise ChartAuthError(
                "Refresh token expired or rejected and no login credentials are configured. "
                "Put fresh access/refresh tokens in .env, delete .token_cache.json and restart.")
        data = await self._post(s.chart_api_login_path,
                                {"username": s.chart_api_username, "password": s.chart_api_password})
        self._store(data)
        logger.info("Chart API login successful")

    def _store(self, data: dict) -> None:
        access = _pick(data, "access_token", "accessToken", "access")
        if not access:
            raise ChartAuthError("Auth response did not contain an access token.")
        self._access = access
        # Refresh token may rotate; keep the new one if given, else keep the old one
        self._refresh = _pick(data, "refresh_token", "refreshToken", "refresh") or self._refresh

        expires_in = data.get("expires_in") or data.get("expiresIn")
        if expires_in:
            self._expires_at = time.time() + float(expires_in)
        else:
            self._expires_at = _jwt_expiry(access) or (time.time() + DEFAULT_LIFETIME_SECONDS)
        self._save_cache()

    async def _post(self, path: str, payload: dict) -> dict:
        s = get_settings()
        url = s.chart_api_base_url.rstrip("/") + path
        try:
            async with httpx.AsyncClient(timeout=s.chart_api_timeout_seconds) as client:
                resp = await client.post(url, json=payload)
        except httpx.TransportError as exc:
            raise ChartServiceError() from exc

        if resp.status_code in (400, 401, 403):
            raise ChartAuthError()          # credentials/refresh token rejected
        if resp.status_code >= 400:
            raise ChartServiceError()
        try:
            return resp.json()
        except ValueError as exc:
            raise ChartAuthError("Auth response was not valid JSON.") from exc


_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    global _manager
    if _manager is None:
        _manager = TokenManager()
    return _manager