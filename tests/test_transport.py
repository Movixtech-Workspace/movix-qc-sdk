import base64
import json

import httpx
import pytest
import respx

from movix_qc_sdk.client import Client
from movix_qc_sdk.errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
)
from movix_qc_sdk.transport import Transport
from movix_qc_sdk.transport import redact_headers


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


def _make_transport() -> Transport:
    return Transport(
        api_url="https://api.test",
        timeout_s=5.0,
        retries=0,
        user_agent="ua",
        token_provider=None,
    )


def test_redact_headers():
    headers = {
        "Authorization": "Bearer token",
        "Cookie": "session=1",
        "Set-Cookie": "session=2",
        "X-Trace": "trace",
    }

    redacted = redact_headers(headers)

    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Cookie"] == "[REDACTED]"
    assert redacted["Set-Cookie"] == "[REDACTED]"
    assert redacted["X-Trace"] == "trace"


@respx.mock
def test_request_json_maps_status_codes():
    transport = _make_transport()
    try:
        respx.get("https://api.test/forbidden").mock(
            return_value=httpx.Response(403, json={"message": "forbidden"})
        )
        with pytest.raises(AuthorizationError) as excinfo:
            transport.request_json("GET", "/forbidden")
        assert str(excinfo.value) == "forbidden"

        respx.get("https://api.test/missing").mock(
            return_value=httpx.Response(404, json={"error": "missing"})
        )
        with pytest.raises(NotFoundError) as excinfo:
            transport.request_json("GET", "/missing")
        assert str(excinfo.value) == "missing"

        respx.get("https://api.test/rate").mock(
            return_value=httpx.Response(429, json={"error": "slow down"})
        )
        with pytest.raises(RateLimitError) as excinfo:
            transport.request_json("GET", "/rate")
        assert str(excinfo.value) == "slow down"

        respx.get("https://api.test/auth").mock(
            return_value=httpx.Response(401, json={"error": "nope"})
        )
        with pytest.raises(AuthenticationError) as excinfo:
            transport.request_json("GET", "/auth")
        assert str(excinfo.value) == "nope"
    finally:
        transport.close()


@respx.mock
def test_request_json_network_error():
    transport = _make_transport()
    try:
        def _boom(request):
            raise httpx.ConnectError("boom", request=request)

        respx.get("https://api.test/network").mock(side_effect=_boom)
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/network")
        assert str(excinfo.value) == "Request failed due to a network error."
    finally:
        transport.close()


@respx.mock
def test_request_json_invalid_json_response():
    transport = _make_transport()
    try:
        respx.get("https://api.test/json").mock(
            return_value=httpx.Response(200, content=b"not-json")
        )
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/json")
        assert str(excinfo.value) == "Unexpected response from API."
    finally:
        transport.close()


@respx.mock
def test_request_json_uses_safe_error_message():
    transport = _make_transport()
    try:
        # Non-JSON response - fallback to status message
        respx.get("https://api.test/bad").mock(
            return_value=httpx.Response(500, content=b"no-json")
        )
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/bad")
        assert str(excinfo.value) == "Request failed with status 500."

        # JSON with "error" field
        respx.get("https://api.test/error").mock(
            return_value=httpx.Response(400, json={"error": "Custom error message"})
        )
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/error")
        assert str(excinfo.value) == "Custom error message"

        # JSON with "message" field
        respx.get("https://api.test/message").mock(
            return_value=httpx.Response(400, json={"message": "Custom message"})
        )
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/message")
        assert str(excinfo.value) == "Custom message"

        # JSON without error/message - fallback to status
        respx.get("https://api.test/nofield").mock(
            return_value=httpx.Response(503, json={"status": "unavailable"})
        )
        with pytest.raises(ApiError) as excinfo:
            transport.request_json("GET", "/nofield")
        assert str(excinfo.value) == "Request failed with status 503."
    finally:
        transport.close()


@respx.mock
def test_auth_header_injection(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

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

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.get("case-1")
    assert case.case_id == "case-1"

    request = list_route.calls[0].request
    assert request.headers.get("Authorization") == f"Bearer {access}"
    client.close()


@respx.mock
def test_refresh_on_401(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access1 = _make_jwt(now + 120)
    access2 = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access1, "refresh": "r1"})
    )
    refresh_route = respx.post("https://api.test/api/v1/auth/token/refresh/").mock(
        return_value=httpx.Response(200, json={"access": access2, "refresh": "r2"})
    )

    list_route = respx.get("https://api.test/api/v1/base/cases/").mock(
        side_effect=[
            httpx.Response(401, json={"error": "invalid token"}),
            httpx.Response(
                200,
                json={
                    "cases": [
                        {"case_id": "case-1", "created_at": "2024-01-01T00:00:00Z"}
                    ]
                },
            ),
        ]
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.get("case-1")
    assert case.case_id == "case-1"

    assert refresh_route.called
    assert len(list_route.calls) == 2
    client.close()


@respx.mock
def test_retry_on_rate_limit(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    list_route = respx.get("https://api.test/api/v1/base/cases/").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(
                200,
                json={
                    "cases": [
                        {"case_id": "case-1", "created_at": "2024-01-01T00:00:00Z"}
                    ]
                },
            ),
        ]
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.get("case-1")
    assert case.case_id == "case-1"
    assert len(list_route.calls) == 2
    client.close()


@respx.mock
def test_retry_on_server_error(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    list_route = respx.get("https://api.test/api/v1/base/cases/").mock(
        side_effect=[
            httpx.Response(500, json={"error": "server error"}),
            httpx.Response(
                200,
                json={
                    "cases": [
                        {"case_id": "case-1", "created_at": "2024-01-01T00:00:00Z"}
                    ]
                },
            ),
        ]
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.get("case-1")
    assert case.case_id == "case-1"
    assert len(list_route.calls) == 2
    client.close()
