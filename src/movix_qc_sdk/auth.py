"""Authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Protocol
import base64

import httpx

from movix_qc_sdk.errors import AuthenticationError, ApiError


@dataclass
class TokenData:
    """In-memory token data."""

    access_token: str
    refresh_token: str | None
    access_expires_at: float | None


class TokenCache(Protocol):
    """Optional token persistence interface."""

    def load(self) -> TokenData | None:
        ...

    def save(self, token_data: TokenData) -> None:
        ...


class TokenProvider(Protocol):
    """Protocol for token providers used by the client."""

    def get_access_token(self) -> str:
        ...

    def refresh_access_token(self) -> str:
        ...


def _decode_jwt_exp(access_token: str) -> float | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        payload_data = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None
    exp = payload_data.get("exp")
    if isinstance(exp, (int, float)):
        return float(exp)
    return None


def _extract_expires_at(payload: dict[str, Any], access_token: str) -> float | None:
    now = time.time()
    for key in ("expires_in", "access_expires_in"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return now + float(value)
    return _decode_jwt_exp(access_token)


class PasswordTokenProvider:
    """Token provider that logs in with username and password."""

    def __init__(
        self,
        api_url: str,
        username: str,
        password: str,
        timeout_s: float,
        user_agent: str,
        token_cache: TokenCache | None = None,
    ) -> None:
        self._api_url = api_url
        self._username = username
        self._password = password
        self._timeout_s = timeout_s
        self._user_agent = user_agent
        self._token_cache = token_cache
        self._token_data = token_cache.load() if token_cache else None
        self._expiry_buffer_s = 60.0
        self._client = httpx.Client(
            base_url=api_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
        )

    def get_access_token(self) -> str:
        token_data = self._token_data
        if token_data is None:
            token_data = self._login()
        elif self._is_expired(token_data.access_expires_at):
            token_data = self._refresh_or_login(token_data)
        self._token_data = token_data
        if self._token_cache:
            self._token_cache.save(token_data)
        return token_data.access_token

    def refresh_access_token(self) -> str:
        token_data = self._token_data
        if token_data is None:
            token_data = self._login()
        else:
            token_data = self._refresh_or_login(token_data)
        self._token_data = token_data
        if self._token_cache:
            self._token_cache.save(token_data)
        return token_data.access_token

    def close(self) -> None:
        self._client.close()

    def _is_expired(self, expires_at: float | None) -> bool:
        if expires_at is None:
            return False
        return time.time() >= (expires_at - self._expiry_buffer_s)

    def _login(self) -> TokenData:
        response = self._client.post(
            "/api/v1/auth/login/",
            json={"username": self._username, "password": self._password},
        )
        if response.status_code != 200:
            raise AuthenticationError("Login failed.")
        payload = _parse_json(response)
        access_token = payload.get("access")
        refresh_token = payload.get("refresh")
        if not isinstance(access_token, str):
            raise AuthenticationError("Login did not return an access token.")
        expires_at = _extract_expires_at(payload, access_token)
        return TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=expires_at,
        )

    def _refresh_or_login(self, token_data: TokenData) -> TokenData:
        if token_data.refresh_token is None:
            return self._login()
        try:
            return self._refresh(token_data.refresh_token)
        except AuthenticationError:
            return self._login()

    def _refresh(self, refresh_token: str) -> TokenData:
        response = self._client.post(
            "/api/v1/auth/token/refresh/",
            json={"refresh": refresh_token},
        )
        if response.status_code != 200:
            raise AuthenticationError("Token refresh failed.")
        payload = _parse_json(response)
        access_token = payload.get("access")
        if not isinstance(access_token, str):
            raise AuthenticationError("Refresh did not return an access token.")
        new_refresh_token = payload.get("refresh", refresh_token)
        expires_at = _extract_expires_at(payload, access_token)
        return TokenData(
            access_token=access_token,
            refresh_token=new_refresh_token,
            access_expires_at=expires_at,
        )


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ApiError("Unexpected response from authentication endpoint.") from exc
    if not isinstance(payload, dict):
        raise ApiError("Unexpected response from authentication endpoint.")
    return payload
