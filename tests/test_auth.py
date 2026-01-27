import base64
import json

import httpx
import pytest
import respx

from movix_qc_sdk.auth import PasswordTokenProvider, TokenData
from movix_qc_sdk.errors import AuthenticationError


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


@respx.mock
def test_login_and_refresh(monkeypatch):
    now = 1_700_000_000
    access1 = _make_jwt(now + 120)
    access2 = _make_jwt(now + 3600)

    login_route = respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access1, "refresh": "r1"})
    )
    refresh_route = respx.post("https://api.test/api/v1/auth/token/refresh/").mock(
        return_value=httpx.Response(200, json={"access": access2, "refresh": "r2"})
    )

    provider = PasswordTokenProvider(
        api_url="https://api.test",
        username="user",
        password="pass",
        timeout_s=5.0,
        user_agent="ua",
    )

    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)
    token = provider.get_access_token()
    assert token == access1

    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now + 61)
    token = provider.get_access_token()
    assert token == access2

    assert login_route.called
    assert refresh_route.called
    provider.close()


@respx.mock
def test_login_failure_invalid_credentials():
    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(401, json={"error": "bad creds"})
    )

    provider = PasswordTokenProvider(
        api_url="https://api.test",
        username="user",
        password="pass",
        timeout_s=5.0,
        user_agent="ua",
    )

    with pytest.raises(AuthenticationError) as excinfo:
        provider.get_access_token()
    assert str(excinfo.value) == "Login failed."
    provider.close()


@respx.mock
def test_expired_token_without_refresh_logs_in(monkeypatch):
    now = 1_700_000_000
    access_old = _make_jwt(now + 10)
    access_new = _make_jwt(now + 3600)

    login_route = respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access_new, "refresh": "r1"})
    )

    class _StaticTokenCache:
        def __init__(self, token_data):
            self._token_data = token_data

        def load(self):
            return self._token_data

        def save(self, token_data):
            self._token_data = token_data

    token_cache = _StaticTokenCache(
        TokenData(
            access_token=access_old,
            refresh_token=None,
            access_expires_at=now + 10,
        )
    )

    provider = PasswordTokenProvider(
        api_url="https://api.test",
        username="user",
        password="pass",
        timeout_s=5.0,
        user_agent="ua",
        token_cache=token_cache,
    )

    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now + 120)
    token = provider.get_access_token()
    assert token == access_new
    assert login_route.called
    provider.close()


def test_jwt_parsing_malformed_token():
    from movix_qc_sdk.auth import _decode_jwt_exp

    # JWT with only 1 part (should have 3)
    assert _decode_jwt_exp("single_part") is None

    # JWT with 2 parts (missing signature)
    assert _decode_jwt_exp("header.payload") is None

    # JWT with invalid base64 in payload
    assert _decode_jwt_exp("header.!!!invalid!!!.signature") is None


def test_jwt_parsing_exp_not_number():
    from movix_qc_sdk.auth import _decode_jwt_exp

    # JWT with exp as string
    payload = {"exp": "not_a_number"}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    jwt = f"header.{payload_b64.decode()}.signature"
    assert _decode_jwt_exp(jwt) is None

    # JWT without exp field
    payload = {"user": "test"}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    jwt = f"header.{payload_b64.decode()}.signature"
    assert _decode_jwt_exp(jwt) is None


@respx.mock
def test_custom_token_provider(monkeypatch):
    from movix_qc_sdk.client import Client

    class StaticTokenProvider:
        """Simple custom token provider for testing."""

        def __init__(self, token: str):
            self._token = token

        def get_access_token(self) -> str:
            return self._token

        def refresh_access_token(self) -> str:
            return self._token

    custom_provider = StaticTokenProvider("custom-token-123")

    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)

    list_route = respx.get("https://api.test/api/v1/base/cases/").mock(
        return_value=httpx.Response(
            200,
            json={
                "cases": [
                    {"case_id": "case-1", "created_at": "2024-01-01T00:00:00Z"}
                ]
            },
        )
    )

    client = Client(
        api_url="https://api.test",
        username="user",
        password="pass",
        token_provider=custom_provider,
    )

    case = client.cases.get("case-1")
    assert case.case_id == "case-1"

    # Verify custom token was used
    request = list_route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer custom-token-123"

    client.close()
