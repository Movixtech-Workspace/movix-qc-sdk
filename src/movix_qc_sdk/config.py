"""SDK configuration resolution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse

from movix_qc_sdk.errors import ValidationError


ENV_API_URL = "MOVIX_QC_API_URL"
ENV_USERNAME = "MOVIX_QC_USERNAME"
ENV_PASSWORD = "MOVIX_QC_PASSWORD"
ENV_TIMEOUT = "MOVIX_QC_TIMEOUT"
ENV_RETRIES = "MOVIX_QC_RETRIES"
ENV_USER_AGENT = "MOVIX_QC_USER_AGENT"


@dataclass(frozen=True)
class Config:
    """Resolved SDK configuration."""

    api_url: str
    username: str | None
    password: str | None
    timeout_s: float
    retries: int
    user_agent: str


def _parse_timeout(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Timeout must be a number of seconds.")
    if timeout <= 0:
        raise ValidationError("Timeout must be greater than zero.")
    return timeout


def _parse_retries(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        retries = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Retries must be an integer.")
    if retries < 0:
        raise ValidationError("Retries must be zero or greater.")
    return retries


def _validate_api_url(value: str | None) -> str:
    if not value:
        raise ValidationError("api_url is required.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("api_url must be a valid http(s) URL.")
    return value.rstrip("/")


def resolve_config(
    api_url: str | None,
    username: str | None,
    password: str | None,
    timeout_s: float | None,
    retries: int | None,
    user_agent: str | None,
) -> Config:
    """Resolve configuration from arguments and environment variables."""

    api_url_value = api_url or os.getenv(ENV_API_URL)
    api_url_value = _validate_api_url(api_url_value)

    username_value = username or os.getenv(ENV_USERNAME)
    password_value = password or os.getenv(ENV_PASSWORD)

    timeout_value = _parse_timeout(
        str(timeout_s) if timeout_s is not None else os.getenv(ENV_TIMEOUT),
        default=45.0,
    )
    retries_value = _parse_retries(
        str(retries) if retries is not None else os.getenv(ENV_RETRIES),
        default=10,
    )

    user_agent_value = user_agent or os.getenv(ENV_USER_AGENT) or "movix-qc-sdk/0.1.0"

    return Config(
        api_url=api_url_value,
        username=username_value,
        password=password_value,
        timeout_s=timeout_value,
        retries=retries_value,
        user_agent=user_agent_value,
    )
