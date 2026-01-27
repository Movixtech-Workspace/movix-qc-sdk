import base64
import json

import httpx
import pytest
import respx

from movix_qc_sdk.client import Client
from movix_qc_sdk.errors import MovixQCError, ValidationError
from movix_qc_sdk.models import TaskStatus


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


@respx.mock
def test_wait_polls_until_complete(monkeypatch):
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/9").mock(
        side_effect=[
            httpx.Response(200, json={"id": 9, "status": "Run"}),
            httpx.Response(200, json={"id": 9, "status": "Done"}),
        ]
    )

    monkeypatch.setattr("movix_qc_sdk.tasks.time.sleep", lambda *_: None)
    counter = {"value": 0.0}

    def _monotonic():
        counter["value"] += 1.0
        return counter["value"]

    monkeypatch.setattr("movix_qc_sdk.tasks.time.monotonic", _monotonic)

    client = Client(api_url="https://api.test", username="user", password="pass")
    task = client.tasks.wait(
        task_id=9,
        case_id="case-1",
        timeout_s=30.0,
        poll_interval_s=1.0,
    )
    assert task.status == TaskStatus.SUCCEEDED
    client.close()


def test_wait_rejects_invalid_timing():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.wait(task_id=1, case_id="case-1", timeout_s=0)
        with pytest.raises(ValidationError):
            client.tasks.wait(
                task_id=1,
                case_id="case-1",
                timeout_s=10,
                poll_interval_s=0,
            )
    finally:
        client.close()


@respx.mock
def test_wait_times_out(monkeypatch):
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/9").mock(
        return_value=httpx.Response(200, json={"id": 9, "status": "Run"})
    )

    monkeypatch.setattr("movix_qc_sdk.tasks.time.sleep", lambda *_: None)
    counter = {"value": 0.0}

    def _monotonic():
        counter["value"] += 5.0
        return counter["value"]

    monkeypatch.setattr("movix_qc_sdk.tasks.time.monotonic", _monotonic)

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(MovixQCError) as excinfo:
            client.tasks.wait(
                task_id=9,
                case_id="case-1",
                timeout_s=3.0,
                poll_interval_s=1.0,
            )
        assert str(excinfo.value) == "Timed out waiting for task completion."
    finally:
        client.close()


@respx.mock
def test_wait_returns_immediately_on_failed_status(monkeypatch):
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    get_task_route = respx.get("https://api.test/api/v1/services/cases/case-1/tasks/9").mock(
        return_value=httpx.Response(200, json={"id": 9, "status": "Failed"})
    )

    monkeypatch.setattr("movix_qc_sdk.tasks.time.sleep", lambda *_: None)

    client = Client(api_url="https://api.test", username="user", password="pass")
    task = client.tasks.wait(
        task_id=9,
        case_id="case-1",
        timeout_s=30.0,
        poll_interval_s=1.0,
    )
    assert task.status == TaskStatus.FAILED

    # Should only call get_task once (no polling loop)
    assert len(get_task_route.calls) == 1

    client.close()
