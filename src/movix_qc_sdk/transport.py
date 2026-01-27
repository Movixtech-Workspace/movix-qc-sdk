"""HTTP transport with retries and auth handling."""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from movix_qc_sdk.auth import TokenProvider
from movix_qc_sdk.errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
)


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive headers for safe logging."""

    redacted = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in {"authorization", "cookie", "set-cookie"}:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


class Transport:
    """HTTP transport with retries and token refresh."""

    def __init__(
        self,
        api_url: str,
        timeout_s: float,
        retries: int,
        user_agent: str,
        token_provider: TokenProvider | None,
    ) -> None:
        self._timeout_s = timeout_s
        self._retries = retries
        self._token_provider = token_provider
        self._client = httpx.Client(
            base_url=api_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
        )
        self._max_backoff_s = 8.0

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> httpx.Response:
        timeout = timeout_s if timeout_s is not None else self._timeout_s
        request_headers = dict(headers or {})

        auth_attempted = False

        response: httpx.Response | None = None
        for attempt in range(self._retries + 1):
            if self._token_provider:
                token = self._token_provider.get_access_token()
                request_headers["Authorization"] = f"Bearer {token}"

            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=request_headers,
                    timeout=timeout,
                )
            except httpx.RequestError as exc:
                if attempt >= self._retries:
                    raise ApiError("Request failed due to a network error.") from exc
                self._sleep_backoff(attempt)
                continue

            if (
                response.status_code == 401
                and self._token_provider
                and not auth_attempted
            ):
                auth_attempted = True
                self._token_provider.refresh_access_token()
                self._sleep_backoff(attempt)
                continue

            if response.status_code in {429} or response.status_code >= 500:
                if attempt >= self._retries:
                    return response
                self._sleep_backoff(attempt)
                continue

            return response

        if response is None:
            raise ApiError("Request failed with no response.")
        return response

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any] | list[Any]:
        response = self.request(
            method,
            path,
            params=params,
            json_body=json_body,
            headers=headers,
            timeout_s=timeout_s,
        )
        self._raise_for_status(response)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ApiError("Unexpected response from API.") from exc

    def _sleep_backoff(self, attempt: int) -> None:
        base = 0.5 * (2 ** attempt)
        jitter = random.random() * 0.25
        time.sleep(min(self._max_backoff_s, base + jitter))

    def _raise_for_status(self, response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return

        message = _safe_error_message(response)
        status_code = response.status_code

        if status_code == 401:
            raise AuthenticationError(message)
        if status_code == 403:
            raise AuthorizationError(message)
        if status_code == 404:
            raise NotFoundError(message)
        if status_code == 429:
            raise RateLimitError(message)
        raise ApiError(message, status_code=status_code)


def _safe_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return f"Request failed with status {response.status_code}."
