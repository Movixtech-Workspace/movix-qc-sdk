import base64
import json

import httpx
import pytest
import respx

from movix_qc_sdk.client import Client
from movix_qc_sdk.errors import TasksNotCompletedError, ValidationError


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


@respx.mock
def test_generate_summary_with_issues(monkeypatch):
    """Test generate_summary returns message when issues are found."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    summary_message = "Hello Doctor,\n\nIssues detected in the scans."
    respx.post("https://api.test/api/v1/services/cases/case-1/summary/").mock(
        return_value=httpx.Response(201, json={"message": summary_message})
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.generate_summary(case_id="case-1")
        assert result.message == summary_message
    finally:
        client.close()


@respx.mock
def test_generate_summary_no_issues(monkeypatch):
    """Test generate_summary returns None message when no issues are found."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.post("https://api.test/api/v1/services/cases/case-1/summary/").mock(
        return_value=httpx.Response(200, json={"message": None})
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.generate_summary(case_id="case-1")
        assert result.message is None
    finally:
        client.close()


@respx.mock
def test_generate_summary_with_language_code(monkeypatch):
    """Test generate_summary with language_code parameter."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    summary_route = respx.post(
        "https://api.test/api/v1/services/cases/case-1/summary/"
    ).mock(return_value=httpx.Response(201, json={"message": "Hola Doctor"}))

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.generate_summary(case_id="case-1", language_code="es")
        assert result.message == "Hola Doctor"

        # Verify request body contains language code
        assert len(summary_route.calls) == 1
        request_body = json.loads(summary_route.calls[0].request.content)
        assert request_body == {"code": "es"}
    finally:
        client.close()


def test_generate_summary_invalid_language_code():
    """Test generate_summary validates language_code type."""
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError) as excinfo:
            client.cases.generate_summary(case_id="case-1", language_code=123)
        assert "language_code must be a string" in str(excinfo.value)
    finally:
        client.close()


@respx.mock
def test_generate_viewer_link_created(monkeypatch):
    """Test generate_viewer_link creates new link (201)."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    viewer_url = "https://viewer.movixtech.com/abc-123?access=token"
    expires_at = "2024-07-28T11:42:12.574133Z"
    respx.post("https://api.test/api/v1/viewer/links/").mock(
        return_value=httpx.Response(
            201,
            json={
                "url": viewer_url,
                "public_id": "abc-123",
                "expires_at": expires_at,
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.generate_viewer_link(case_id="case-1")
        assert result.url == viewer_url
        assert result.public_id == "abc-123"
        assert result.expires_at.year == 2024
    finally:
        client.close()


@respx.mock
def test_generate_viewer_link_existing(monkeypatch):
    """Test generate_viewer_link returns existing link (200)."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    viewer_url = "https://viewer.movixtech.com/abc-123?access=token"
    expires_at = "2024-07-28T11:42:12.574133Z"
    respx.post("https://api.test/api/v1/viewer/links/").mock(
        return_value=httpx.Response(
            200,
            json={
                "url": viewer_url,
                "public_id": "abc-123",
                "expires_at": expires_at,
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.generate_viewer_link(case_id="case-1")
        assert result.url == viewer_url
        assert result.public_id == "abc-123"
    finally:
        client.close()


@respx.mock
def test_generate_viewer_link_tasks_not_completed(monkeypatch):
    """Test generate_viewer_link raises TasksNotCompletedError on 204."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.post("https://api.test/api/v1/viewer/links/").mock(
        return_value=httpx.Response(204)
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(TasksNotCompletedError) as excinfo:
            client.cases.generate_viewer_link(case_id="case-1")
        assert "Required tasks" in str(excinfo.value)
        assert "Occlusal Evaluation" in str(excinfo.value)
        assert "IQC Holes Detection" in str(excinfo.value)
    finally:
        client.close()


@respx.mock
def test_generate_viewer_link_sends_case_id(monkeypatch):
    """Test generate_viewer_link sends case_id in request body."""
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    viewer_route = respx.post("https://api.test/api/v1/viewer/links/").mock(
        return_value=httpx.Response(
            201,
            json={
                "url": "https://viewer.movixtech.com/abc?access=token",
                "public_id": "abc",
                "expires_at": "2024-07-28T11:42:12Z",
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.cases.generate_viewer_link(case_id="case-abc-123")

        # Verify request body contains case_id
        assert len(viewer_route.calls) == 1
        request_body = json.loads(viewer_route.calls[0].request.content)
        assert request_body == {"case_id": "case-abc-123"}
    finally:
        client.close()
