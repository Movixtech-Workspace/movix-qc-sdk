import base64
import json

import httpx
import pytest
import respx

from movix_qc_sdk.client import Client
from movix_qc_sdk.errors import ValidationError
from movix_qc_sdk.models import TaskStatus


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


@respx.mock
def test_tasks_list_and_get(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/").mock(
        return_value=httpx.Response(
            200,
            json={
                "tasks": [
                    {
                        "id": 5,
                        "title": "Task",
                        "status": "Run",
                        "created": "2024-01-01T00:00:00Z",
                    }
                ]
            },
        )
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/5").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 5,
                "title": "Task",
                "status": "Done",
                "created": "2024-01-01T00:00:00Z",
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    tasks = client.tasks.list(case_id="case-1")
    assert tasks[0].status == TaskStatus.RUNNING

    task = client.tasks.get(task_id=5, case_id="case-1")
    assert task.status == TaskStatus.SUCCEEDED
    client.close()


def test_tasks_get_requires_case_id():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.get(task_id=1, case_id=None)
    finally:
        client.close()


@respx.mock
def test_tasks_get_invalid_response(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/5").mock(
        return_value=httpx.Response(200, json=["bad"])
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.get(task_id=5, case_id="case-1")
    finally:
        client.close()


@respx.mock
def test_tasks_list_invalid_response(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/").mock(
        return_value=httpx.Response(200, json={"tasks": "bad"})
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.list(case_id="case-1")
    finally:
        client.close()


@respx.mock
def test_tasks_list_unknown_status_filter(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/").mock(
        return_value=httpx.Response(200, json={"tasks": []})
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.list(case_id="case-1", status="bogus")
    finally:
        client.close()
