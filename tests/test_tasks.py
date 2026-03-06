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

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/5/").mock(
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

    respx.get("https://api.test/api/v1/services/cases/case-1/tasks/5/").mock(
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


@respx.mock
def test_create_occlusion_with_params(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 10,
                "title": "Occlusion Task",
                "status": "created",
                "created_at": "2024-01-01T00:00:00Z",
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        task = client.tasks.create_occlusion(
            "case-1",
            threshold_mm=0.5,
            visualization=False,
            generate_drc=True,
        )
        assert task.task_id == 10
        assert task.status == TaskStatus.QUEUED

        # Verify request payload
        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_mm"] == 0.5
        assert body["visualization"] is False
        assert body["generate_drc"] is True
    finally:
        client.close()


@respx.mock
def test_create_occlusion_uses_config_threshold(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={"id": 11, "title": "Occlusion", "status": "created"},
        )
    )

    client = Client(
        api_url="https://api.test",
        username="user",
        password="pass",
        occlusion_threshold_mm=0.25,
    )
    try:
        client.tasks.create_occlusion("case-1")

        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_mm"] == 0.25
    finally:
        client.close()


@respx.mock
def test_create_holes_with_params(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 20,
                "title": "Holes Task",
                "status": "created",
                "created_at": "2024-01-01T00:00:00Z",
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        task = client.tasks.create_holes(
            "case-1",
            threshold_area_mm=10.5,
            crown_dilation_mm=2.0,
            visualization=False,
            generate_drc=True,
        )
        assert task.task_id == 20
        assert task.status == TaskStatus.QUEUED

        # Verify request payload
        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_area_mm"] == 10.5
        assert body["crown_dilation_mm"] == 2.0
        assert body["visualization"] is False
        assert body["generate_drc"] is True
    finally:
        client.close()


@respx.mock
def test_create_holes_uses_config_threshold(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={"id": 21, "title": "Holes", "status": "created"},
        )
    )

    client = Client(
        api_url="https://api.test",
        username="user",
        password="pass",
        holes_threshold_area_mm=15.0,
    )
    try:
        client.tasks.create_holes("case-1")

        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_area_mm"] == 15.0
        assert "crown_dilation_mm" not in body  # Should not be sent if not specified
    finally:
        client.close()


@respx.mock
def test_create_holes_without_crown_dilation(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={"id": 22, "title": "Holes", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_holes("case-1", threshold_area_mm=5.0)

        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_area_mm"] == 5.0
        assert "crown_dilation_mm" not in body
    finally:
        client.close()


@respx.mock
def test_create_holes_with_zero_crown_dilation(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={"id": 23, "title": "Holes", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_holes("case-1", crown_dilation_mm=0.0)

        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert body["crown_dilation_mm"] == 0.0
    finally:
        client.close()


def test_create_holes_rejects_negative_crown_dilation():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError) as excinfo:
            client.tasks.create_holes("case-1", crown_dilation_mm=-1.0)
        assert "crown_dilation_mm must be zero or greater" in str(excinfo.value)
    finally:
        client.close()


@respx.mock
def test_create_occlusion_with_gap_threshold(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={"id": 12, "title": "Occlusion", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_occlusion("case-1", threshold_mm=0.5, threshold_gap_mm=0.15)

        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_mm"] == 0.5
        assert body["threshold_gap_mm"] == 0.15
    finally:
        client.close()


@respx.mock
def test_create_occlusion_uses_config_gap_threshold(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={"id": 13, "title": "Occlusion", "status": "created"},
        )
    )

    client = Client(
        api_url="https://api.test",
        username="user",
        password="pass",
        occlusion_threshold_gap_mm=0.2,
    )
    try:
        client.tasks.create_occlusion("case-1")

        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert body["threshold_gap_mm"] == 0.2
    finally:
        client.close()


@respx.mock
def test_create_occlusion_with_exclude_crowns(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={"id": 14, "title": "Occlusion", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_occlusion("case-1", exclude_crowns=[18, 28, 38, 48])

        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert body["exclude_crowns"] == [18, 28, 38, 48]
    finally:
        client.close()


@respx.mock
def test_create_occlusion_without_exclude_crowns(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    occlusion_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/hyperocclusion").mock(
        return_value=httpx.Response(
            201,
            json={"id": 15, "title": "Occlusion", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_occlusion("case-1")

        request = occlusion_route.calls.last.request
        body = json.loads(request.content)
        assert "exclude_crowns" not in body
    finally:
        client.close()


def test_create_occlusion_rejects_invalid_exclude_crowns():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.create_occlusion("case-1", exclude_crowns=["bad"])
    finally:
        client.close()


@respx.mock
def test_create_holes_with_exclude_crowns(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={"id": 24, "title": "Holes", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_holes("case-1", exclude_crowns=[18, 28, 38, 48])

        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert body["exclude_crowns"] == [18, 28, 38, 48]
    finally:
        client.close()


@respx.mock
def test_create_holes_without_exclude_crowns(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    holes_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/holes").mock(
        return_value=httpx.Response(
            201,
            json={"id": 25, "title": "Holes", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_holes("case-1")

        request = holes_route.calls.last.request
        body = json.loads(request.content)
        assert "exclude_crowns" not in body
    finally:
        client.close()


def test_create_holes_rejects_invalid_exclude_crowns():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.create_holes("case-1", exclude_crowns="bad")
    finally:
        client.close()


@respx.mock
def test_create_scan_integrity(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    defects_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/defects").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 40,
                "title": "Scan Integrity",
                "status": "created",
                "created_at": "2024-01-01T00:00:00Z",
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        task = client.tasks.create_scan_integrity("case-1")
        assert task.task_id == 40
        assert task.status == TaskStatus.QUEUED

        request = defects_route.calls.last.request
        body = json.loads(request.content)
        assert "exclude_crowns" not in body
    finally:
        client.close()


@respx.mock
def test_create_scan_integrity_with_exclude_crowns(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    defects_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/defects").mock(
        return_value=httpx.Response(
            201,
            json={"id": 41, "title": "Scan Integrity", "status": "created"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        client.tasks.create_scan_integrity("case-1", exclude_crowns=[18, 28, 38, 48])

        request = defects_route.calls.last.request
        body = json.loads(request.content)
        assert body["exclude_crowns"] == [18, 28, 38, 48]
    finally:
        client.close()


def test_create_scan_integrity_rejects_invalid_exclude_crowns():
    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.tasks.create_scan_integrity("case-1", exclude_crowns=[1.5])
    finally:
        client.close()


@respx.mock
def test_create_data_validation(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    validation_route = respx.post("https://api.test/api/v1/services/cases/case-1/tasks/").mock(
        return_value=httpx.Response(
            201,
            json={"id": 30, "title": "Data Validation", "status": "done"},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        task = client.tasks.create_data_validation("case-1")
        assert task.task_id == 30
        assert task.status == TaskStatus.SUCCEEDED

        request = validation_route.calls.last.request
        body = json.loads(request.content)
        assert body["service"] == "Data Validation"
    finally:
        client.close()
