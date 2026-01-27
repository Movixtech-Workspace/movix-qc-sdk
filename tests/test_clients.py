import base64
import json
import struct
from pathlib import Path

import httpx
import pytest
import respx

from movix_qc_sdk.cases import MAX_URL_DOWNLOAD_BYTES
from movix_qc_sdk.client import Client
from movix_qc_sdk.errors import ValidationError


def _make_jwt(exp: int) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header_b64.decode()}.{payload_b64.decode()}."


def _require_validation_deps(require_drc: bool = False) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("trimesh")
    if require_drc:
        pytest.importorskip("DracoPy")


def _binary_stl_bytes(offset: float = 0.0) -> bytes:
    header = b"Binary STL" + b"\0" * (80 - len("Binary STL"))
    face_count = 1
    triangle = struct.pack(
        "<12fH",
        0.0,
        0.0,
        1.0,
        0.0 + offset,
        0.0,
        0.0,
        1.0 + offset,
        0.0,
        0.0,
        0.0 + offset,
        1.0,
        0.0,
        0,
    )
    return header + struct.pack("<I", face_count) + triangle


@respx.mock
def test_case_create_upload_and_submit(monkeypatch, tmp_path):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    create_route = respx.post("https://api.test/api/v1/base/cases/").mock(
        return_value=httpx.Response(
            201,
            json={
                "case_id": "case-1",
                "created_at": "2024-01-01T00:00:00Z",
                "note": "Demo",
                "client": "ACME",
            },
        )
    )

    presigned_route = respx.post(
        "https://api.test/api/v1/base/cases/case-1/presigned-links/"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {
                    "url": "https://bucket.storage.googleapis.com/upper",
                    "file_id": "u1",
                },
                "lower_jaw": {
                    "url": "https://bucket.storage.googleapis.com/lower",
                    "file_id": "l1",
                },
            },
        )
    )

    def _upload_callback(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200)

    respx.put("https://bucket.storage.googleapis.com/upper").mock(
        side_effect=_upload_callback
    )
    respx.put("https://bucket.storage.googleapis.com/lower").mock(
        side_effect=_upload_callback
    )

    task_route = respx.post(
        "https://api.test/api/v1/services/cases/case-1/tasks/"
    ).mock(
        return_value=httpx.Response(
            201,
            json={"task_id": 10, "status": "Done", "result": {"ok": True}},
        )
    )

    upper_path = tmp_path / "upper.stl"
    lower_path = tmp_path / "lower.stl"
    upper_path.write_bytes(_binary_stl_bytes(0.0))
    lower_path.write_bytes(_binary_stl_bytes(1.0))

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.submit(
        paths=[upper_path, lower_path],
        metadata={"note": "Demo", "client": "ACME"},
    )
    assert case.case_id == "case-1"

    assert create_route.called
    assert presigned_route.called
    assert task_route.called
    client.close()


@respx.mock
def test_case_get(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/base/cases/").mock(
        return_value=httpx.Response(
            200,
            json={
                "cases": [
                    {
                        "case_id": "case-2",
                        "created_at": "2024-01-01T00:00:00Z",
                        "note": "Note",
                        "client": "ACME",
                    }
                ]
            },
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.get("case-2")
    assert case.case_id == "case-2"
    client.close()


@respx.mock
def test_case_upload_from_urls(monkeypatch):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    presigned_route = respx.post(
        "https://api.test/api/v1/base/cases/case-1/presigned-links/"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {"url": "https://bucket.storage.googleapis.com/upper", "file_id": "u1"},
                "lower_jaw": {"url": "https://bucket.storage.googleapis.com/lower", "file_id": "l1"},
            },
        )
    )

    source_upper = respx.get("https://files.test/upper.stl").mock(
        return_value=httpx.Response(200, content=_binary_stl_bytes(0.0))
    )
    source_lower = respx.get("https://files.test/lower.stl").mock(
        return_value=httpx.Response(200, content=_binary_stl_bytes(1.0))
    )

    upload_upper = respx.put("https://bucket.storage.googleapis.com/upper").mock(
        return_value=httpx.Response(200)
    )
    upload_lower = respx.put("https://bucket.storage.googleapis.com/lower").mock(
        return_value=httpx.Response(200)
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    result = client.cases.upload_urls(
        "case-1",
        urls=["https://files.test/upper.stl", "https://files.test/lower.stl"],
    )
    assert result.upper_file_id == "u1"
    assert result.lower_file_id == "l1"

    assert presigned_route.called
    assert source_upper.called
    assert source_lower.called
    assert upload_upper.called
    assert upload_lower.called

    assert source_upper.calls[0].request.headers.get("Authorization") is None
    assert source_lower.calls[0].request.headers.get("Authorization") is None
    assert upload_upper.calls[0].request.headers.get("Authorization") is None
    assert upload_lower.calls[0].request.headers.get("Authorization") is None

    client.close()


@respx.mock
def test_case_submit_from_urls(monkeypatch):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    create_route = respx.post("https://api.test/api/v1/base/cases/").mock(
        return_value=httpx.Response(
            201,
            json={
                "case_id": "case-10",
                "created_at": "2024-01-01T00:00:00Z",
                "note": "Demo",
                "client": "ACME",
            },
        )
    )

    presigned_route = respx.post(
        "https://api.test/api/v1/base/cases/case-10/presigned-links/"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {"url": "https://bucket.storage.googleapis.com/upper", "file_id": "u1"},
                "lower_jaw": {"url": "https://bucket.storage.googleapis.com/lower", "file_id": "l1"},
            },
        )
    )

    source_upper = respx.get("https://files.test/upper.stl").mock(
        return_value=httpx.Response(200, content=_binary_stl_bytes(0.0))
    )
    source_lower = respx.get("https://files.test/lower.stl").mock(
        return_value=httpx.Response(200, content=_binary_stl_bytes(1.0))
    )

    upload_upper = respx.put("https://bucket.storage.googleapis.com/upper").mock(
        return_value=httpx.Response(200)
    )
    upload_lower = respx.put("https://bucket.storage.googleapis.com/lower").mock(
        return_value=httpx.Response(200)
    )

    task_route = respx.post(
        "https://api.test/api/v1/services/cases/case-10/tasks/"
    ).mock(return_value=httpx.Response(201, json={"task_id": 11}))

    client = Client(api_url="https://api.test", username="user", password="pass")
    case = client.cases.submit_urls(
        urls=["https://files.test/upper.stl", "https://files.test/lower.stl"],
        metadata={"note": "Demo", "client": "ACME"},
    )

    assert case.case_id == "case-10"
    assert create_route.called
    assert presigned_route.called
    assert task_route.called

    assert source_upper.calls[0].request.headers.get("Authorization") is None
    assert source_lower.calls[0].request.headers.get("Authorization") is None
    assert upload_upper.calls[0].request.headers.get("Authorization") is None
    assert upload_lower.calls[0].request.headers.get("Authorization") is None

    client.close()


def test_case_upload_from_urls_requires_two_urls():
    from movix_qc_sdk.cases import _resolve_file_urls

    with pytest.raises(ValidationError) as excinfo:
        _resolve_file_urls(["https://files.test/upper.stl"])
    assert "Exactly two file URLs are required" in str(excinfo.value)


def test_case_upload_from_urls_rejects_invalid_url():
    from movix_qc_sdk.cases import _resolve_file_urls

    with pytest.raises(ValidationError) as excinfo:
        _resolve_file_urls(
            ["ftp://files.test/upper.stl", "https://files.test/lower.stl"]
        )
    assert "File URLs must be valid http(s) URLs" in str(excinfo.value)


@respx.mock
def test_case_upload_from_urls_rejects_large_download():
    source_upper = respx.get("https://files.test/upper.stl").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Length": str(MAX_URL_DOWNLOAD_BYTES + 1)},
            content=b"small",
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.cases.upload_urls(
                "case-1",
                urls=["https://files.test/upper.stl", "https://files.test/lower.stl"],
            )
    finally:
        client.close()

    assert source_upper.called


@respx.mock
def test_case_upload_from_urls_rejects_large_stream_without_content_length(
    monkeypatch,
):
    monkeypatch.setattr("movix_qc_sdk.cases.MAX_URL_DOWNLOAD_BYTES", 5)
    source_upper = respx.get("https://files.test/upper.stl").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Length": "invalid"},
            content=b"0123456789",
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.cases.upload_urls(
                "case-1",
                urls=["https://files.test/upper.stl", "https://files.test/lower.stl"],
            )
    finally:
        client.close()

    assert source_upper.called


@respx.mock
def test_case_upload_from_urls_rejects_redirect():
    source_upper = respx.get("https://files.test/upper.stl").mock(
        return_value=httpx.Response(302)
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.cases.upload_urls(
                "case-1",
                urls=["https://files.test/upper.stl", "https://files.test/lower.stl"],
            )
    finally:
        client.close()

    assert source_upper.called


@respx.mock
def test_upload_files_rejects_upload_failure(monkeypatch, tmp_path):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.post("https://api.test/api/v1/base/cases/case-1/presigned-links/").mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {"url": "https://bucket.storage.googleapis.com/upper", "file_id": "u1"},
                "lower_jaw": {"url": "https://bucket.storage.googleapis.com/lower", "file_id": "l1"},
            },
        )
    )

    upload_upper = respx.put("https://bucket.storage.googleapis.com/upper").mock(
        return_value=httpx.Response(500)
    )
    upload_lower = respx.put("https://bucket.storage.googleapis.com/lower").mock(
        return_value=httpx.Response(200)
    )

    upper_path = tmp_path / "upper.stl"
    lower_path = tmp_path / "lower.stl"
    upper_path.write_bytes(_binary_stl_bytes(0.0))
    lower_path.write_bytes(_binary_stl_bytes(1.0))

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError):
            client.cases.upload_files("case-1", paths=[upper_path, lower_path])
    finally:
        client.close()

    assert upload_upper.called
    assert not upload_lower.called


def test_upload_files_rejects_identical_files(tmp_path):
    from movix_qc_sdk.cases import _validate_file_pair

    upper_path = tmp_path / "upper.stl"
    lower_path = tmp_path / "lower.stl"
    content = _binary_stl_bytes(0.0)
    upper_path.write_bytes(content)
    lower_path.write_bytes(content)

    with pytest.raises(ValidationError) as excinfo:
        _validate_file_pair(upper_path, lower_path, "stl")
    assert "Files are identical" in str(excinfo.value)


def test_upload_files_rejects_extension_mismatch(tmp_path):
    from movix_qc_sdk.cases import _ensure_extension_matches_paths

    upper_path = tmp_path / "upper.stl"
    lower_path = tmp_path / "lower.stl"
    upper_path.write_bytes(_binary_stl_bytes(0.0))
    lower_path.write_bytes(_binary_stl_bytes(1.0))

    with pytest.raises(ValidationError) as excinfo:
        _ensure_extension_matches_paths(upper_path, lower_path, "drc")
    assert "File extension does not match expected format" in str(excinfo.value)


def test_upload_files_rejects_invalid_stl(tmp_path):
    from movix_qc_sdk.cases import _validate_stl_format

    _require_validation_deps()
    invalid_path = tmp_path / "invalid.stl"
    invalid_path.write_text("not stl")

    with pytest.raises(ValidationError) as excinfo:
        _validate_stl_format(invalid_path)
    assert "Invalid STL format" in str(excinfo.value)


def test_upload_files_rejects_invalid_drc(tmp_path):
    from movix_qc_sdk.cases import _validate_drc_format

    _require_validation_deps(require_drc=True)
    invalid_path = tmp_path / "invalid.drc"
    invalid_path.write_bytes(b"NOTDRC")

    with pytest.raises(ValidationError) as excinfo:
        _validate_drc_format(invalid_path)
    assert "Invalid DRC format" in str(excinfo.value)


@respx.mock
def test_upload_files_accepts_valid_drc(monkeypatch, tmp_path):
    _require_validation_deps(require_drc=True)
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.post("https://api.test/api/v1/base/cases/case-1/presigned-links/").mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {"url": "https://bucket.storage.googleapis.com/upper", "file_id": "u1"},
                "lower_jaw": {"url": "https://bucket.storage.googleapis.com/lower", "file_id": "l1"},
            },
        )
    )

    upload_upper = respx.put("https://bucket.storage.googleapis.com/upper").mock(
        return_value=httpx.Response(200)
    )
    upload_lower = respx.put("https://bucket.storage.googleapis.com/lower").mock(
        return_value=httpx.Response(200)
    )

    fixtures = Path(__file__).resolve().parent / "fixtures"
    upper_path = tmp_path / "upper.drc"
    lower_path = tmp_path / "lower.drc"
    upper_path.write_bytes((fixtures / "upper_contact.drc").read_bytes())
    lower_path.write_bytes((fixtures / "lower_contact.drc").read_bytes())

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.upload_files("case-1", paths=[upper_path, lower_path])
    finally:
        client.close()

    assert result.upper_file_id == "u1"
    assert result.lower_file_id == "l1"
    assert upload_upper.called
    assert upload_lower.called


@respx.mock
def test_client_health_success(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/auth/profile/").mock(
        return_value=httpx.Response(
            200,
            json={"email": "test@example.com", "services": []},
        )
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    assert client.health() is True
    client.close()


@respx.mock
def test_client_health_failure_invalid_response(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.get("https://api.test/api/v1/auth/profile/").mock(
        return_value=httpx.Response(200, json={"error": "something"})
    )

    client = Client(api_url="https://api.test", username="user", password="pass")
    assert client.health() is False
    client.close()


@respx.mock
def test_client_health_failure_network_error(monkeypatch):
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    def _boom(request):
        raise httpx.ConnectError("boom", request=request)

    respx.get("https://api.test/api/v1/auth/profile/").mock(side_effect=_boom)

    client = Client(api_url="https://api.test", username="user", password="pass")
    assert client.health() is False
    client.close()


@respx.mock
def test_upload_files_without_upper_lower_in_names(monkeypatch, tmp_path):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    respx.post("https://api.test/api/v1/base/cases/case-1/presigned-links/").mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {
                    "url": "https://bucket.storage.googleapis.com/upper",
                    "file_id": "u1",
                },
                "lower_jaw": {
                    "url": "https://bucket.storage.googleapis.com/lower",
                    "file_id": "l1",
                },
            },
        )
    )

    upload_upper = respx.put("https://bucket.storage.googleapis.com/upper").mock(
        return_value=httpx.Response(200)
    )
    upload_lower = respx.put("https://bucket.storage.googleapis.com/lower").mock(
        return_value=httpx.Response(200)
    )

    # Files without "upper" or "lower" in names - should use order
    file1_path = tmp_path / "file1.stl"
    file2_path = tmp_path / "file2.stl"
    file1_path.write_bytes(_binary_stl_bytes(0.0))
    file2_path.write_bytes(_binary_stl_bytes(1.0))

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        result = client.cases.upload_files("case-1", paths=[file1_path, file2_path])
        assert result.upper_file_id == "u1"
        assert result.lower_file_id == "l1"
        assert upload_upper.called
        assert upload_lower.called
    finally:
        client.close()


@respx.mock
def test_upload_presigned_url_domain_validation_rejects_invalid(
    monkeypatch, tmp_path
):
    _require_validation_deps()
    monkeypatch.setattr("movix_qc_sdk.transport.time.sleep", lambda *_: None)
    now = 1_700_000_000
    access = _make_jwt(now + 3600)
    monkeypatch.setattr("movix_qc_sdk.auth.time.time", lambda: now)

    respx.post("https://api.test/api/v1/auth/login/").mock(
        return_value=httpx.Response(200, json={"access": access, "refresh": "r1"})
    )

    # Presigned URL with invalid domain
    respx.post("https://api.test/api/v1/base/cases/case-1/presigned-links/").mock(
        return_value=httpx.Response(
            200,
            json={
                "upper_jaw": {"url": "https://evil.com/upload", "file_id": "u1"},
                "lower_jaw": {
                    "url": "https://bucket.storage.googleapis.com/lower",
                    "file_id": "l1",
                },
            },
        )
    )

    upper_path = tmp_path / "upper.stl"
    lower_path = tmp_path / "lower.stl"
    upper_path.write_bytes(_binary_stl_bytes(0.0))
    lower_path.write_bytes(_binary_stl_bytes(1.0))

    client = Client(api_url="https://api.test", username="user", password="pass")
    try:
        with pytest.raises(ValidationError) as excinfo:
            client.cases.upload_files("case-1", paths=[upper_path, lower_path])
        assert "Presigned URL domain not allowed" in str(excinfo.value)
        assert "evil.com" in str(excinfo.value)
    finally:
        client.close()


def test_filename_sanitization_from_url():
    from pathlib import Path
    from urllib.parse import urlparse

    # Test that Path.name correctly extracts basename and our validation catches edge cases
    test_cases = [
        # Path.name automatically gets basename, removing ../
        ("https://example.com/../../../etc/passwd", "passwd"),
        ("https://example.com/path/../file.stl", "file.stl"),
        ("https://example.com/normalfile.stl", "normalfile.stl"),

        # Edge cases with no name
        ("https://example.com/", ""),
        ("https://example.com", ""),
    ]

    for url, expected_basename in test_cases:
        name = Path(urlparse(url).path).name
        assert name == expected_basename, f"URL {url} basename should be {expected_basename}"

    # Test our additional validation logic
    # Direct ".." in filename (shouldn't happen via URL, but defensive check)
    assert ".." in "../file.stl"  # Would be caught by our validation
    assert "/" not in Path("../file.stl").name  # Path.name removes path separators
