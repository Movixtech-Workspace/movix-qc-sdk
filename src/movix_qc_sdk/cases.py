"""Case resources."""

from __future__ import annotations

from typing import Iterable
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import tempfile

import httpx

from movix_qc_sdk.errors import NotFoundError, TasksNotCompletedError, ValidationError
from movix_qc_sdk.models import Case, SummaryResult, UploadResult, ViewerLink
from movix_qc_sdk.transport import Transport


MAX_URL_DOWNLOAD_BYTES = 256 * 1024 * 1024

# Allowed storage domains for presigned URL validation
ALLOWED_STORAGE_DOMAIN_SUFFIXES = [
    ".storage.googleapis.com",
]


class CasesClient:
    """Client for case-related operations."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create(self, note: str | None = None, client: str | None = None) -> Case:
        """Create a new case."""

        payload: dict[str, str] = {}
        if note is not None:
            if not isinstance(note, str):
                raise ValidationError("note must be a string.")
            payload["note"] = note
        if client is not None:
            if not isinstance(client, str):
                raise ValidationError("client must be a string.")
            payload["client"] = client

        data = self._transport.request_json(
            "POST",
            "/api/v1/base/cases/",
            json_body=payload,
        )
        return Case.model_validate(data)

    def get(self, case_id: str) -> Case:
        """Get a case by ID."""

        cases = self._list_cases()
        for case in cases:
            if case.case_id == case_id:
                return case
        raise NotFoundError("Case not found.")

    def upload_files(
        self,
        case_id: str,
        paths: Iterable[str | Path],
        extension: str | None = None,
        timeout_s: float | None = None,
    ) -> UploadResult:
        """Upload upper and lower files for a case using presigned URLs."""

        upper_path, lower_path = _resolve_file_paths(paths)
        ext = _resolve_extension(upper_path, lower_path, extension)
        file_type = _resolve_file_type_from_paths(upper_path, lower_path, extension)
        _validate_file_pair(upper_path, lower_path, file_type)
        params = {"extension": ext} if ext else None
        data = self._transport.request_json(
            "POST",
            f"/api/v1/base/cases/{case_id}/presigned-links/",
            params=params,
        )
        upper_info = data.get("upper_jaw")
        lower_info = data.get("lower_jaw")
        if not isinstance(upper_info, dict) or not isinstance(lower_info, dict):
            raise ValidationError("Presigned link response is missing file data.")

        upper_url = upper_info.get("url")
        lower_url = lower_info.get("url")
        upper_file_id = upper_info.get("file_id")
        lower_file_id = lower_info.get("file_id")
        if not all(
            isinstance(value, str)
            for value in [upper_url, lower_url, upper_file_id, lower_file_id]
        ):
            raise ValidationError("Presigned link response is invalid.")

        _upload_presigned(upper_url, upper_path, timeout_s)
        _upload_presigned(lower_url, lower_path, timeout_s)

        return UploadResult(
            case_id=case_id,
            upper_file_id=upper_file_id,
            lower_file_id=lower_file_id,
        )

    def upload_urls(
        self,
        case_id: str,
        urls: Iterable[str],
        extension: str | None = None,
        timeout_s: float | None = None,
    ) -> UploadResult:
        """Upload upper and lower files from public URLs using presigned URLs."""

        upper_url, lower_url = _resolve_file_urls(urls)
        ext = _resolve_url_extension(upper_url, lower_url, extension)
        file_type = _resolve_file_type_from_urls(upper_url, lower_url, extension)

        with tempfile.TemporaryDirectory(prefix="movix-qc-sdk-") as tmp_dir:
            upper_path = _download_url_to_path(
                upper_url,
                Path(tmp_dir),
                file_type,
                "upper",
                timeout_s,
            )
            lower_path = _download_url_to_path(
                lower_url,
                Path(tmp_dir),
                file_type,
                "lower",
                timeout_s,
            )
            _validate_file_pair(upper_path, lower_path, file_type)

            params = {"extension": ext} if ext else None
            data = self._transport.request_json(
                "POST",
                f"/api/v1/base/cases/{case_id}/presigned-links/",
                params=params,
            )
            upper_info = data.get("upper_jaw")
            lower_info = data.get("lower_jaw")
            if not isinstance(upper_info, dict) or not isinstance(lower_info, dict):
                raise ValidationError("Presigned link response is missing file data.")

            upper_upload_url = upper_info.get("url")
            lower_upload_url = lower_info.get("url")
            upper_file_id = upper_info.get("file_id")
            lower_file_id = lower_info.get("file_id")
            if not all(
                isinstance(value, str)
                for value in [
                    upper_upload_url,
                    lower_upload_url,
                    upper_file_id,
                    lower_file_id,
                ]
            ):
                raise ValidationError("Presigned link response is invalid.")

            _upload_presigned(upper_upload_url, upper_path, timeout_s)
            _upload_presigned(lower_upload_url, lower_path, timeout_s)

            return UploadResult(
                case_id=case_id,
                upper_file_id=upper_file_id,
                lower_file_id=lower_file_id,
            )

    def submit(
        self,
        paths: Iterable[str | Path],
        metadata: dict[str, str] | None = None,
        extension: str | None = None,
    ) -> Case:
        """Create a case, upload files, and start the default validation task."""

        metadata = metadata or {}
        note = metadata.get("note")
        client = metadata.get("client")
        case = self.create(note=note, client=client)
        self.upload_files(case.case_id, paths=paths, extension=extension)
        self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case.case_id}/tasks/",
        )
        return case

    def submit_urls(
        self,
        urls: Iterable[str],
        metadata: dict[str, str] | None = None,
        extension: str | None = None,
    ) -> Case:
        """Create a case, upload files from URLs, and start validation."""

        metadata = metadata or {}
        note = metadata.get("note")
        client = metadata.get("client")
        case = self.create(note=note, client=client)
        self.upload_urls(case.case_id, urls=urls, extension=extension)
        self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case.case_id}/tasks/",
        )
        return case

    def generate_summary(
        self,
        case_id: str,
        language_code: str | None = None,
    ) -> SummaryResult:
        """Generate a result summary for a case.

        Call this after all validation tasks (Data Validation, Occlusion, Holes) are complete.
        The summary aggregates outcomes from individual validations.

        Arguments:
            case_id: required case UUID as a string.
            language_code: optional language code (e.g., "en", "es", "de").
                If not provided, uses the user's language or default language.

        Returns:
            SummaryResult with a message field (str if issues found, None otherwise).

        Raises:
            ValidationError: if case_id is invalid or API response is malformed.
            ApiError: for API errors (404 if case not found, 403 if access denied).
        """
        payload = {}
        if language_code is not None:
            if not isinstance(language_code, str):
                raise ValidationError("language_code must be a string.")
            payload["code"] = language_code.strip()

        data = self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case_id}/summary/",
            json_body=payload if payload else None,
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when generating summary.")

        return SummaryResult.model_validate(data)

    def generate_viewer_link(self, case_id: str) -> ViewerLink:
        """Generate a secure viewer link for a case.

        Call this after Occlusal Evaluation and IQC Holes Detection tasks are complete.
        The link allows sharing visualization results with external viewers.

        Arguments:
            case_id: required case UUID as a string.

        Returns:
            ViewerLink with url, public_id, and expires_at fields.

        Raises:
            TasksNotCompletedError: if required tasks (Occlusal Evaluation and IQC Holes Detection) are not complete.
            ValidationError: if case_id is invalid or API response is malformed.
            ApiError: for API errors (404 if case not found, 403 if access denied).
        """
        response = self._transport.request(
            "POST",
            "/api/v1/viewer/links/",
            json_body={"case_id": case_id},
        )

        # 204 No Content = required tasks not yet completed
        if response.status_code == 204:
            raise TasksNotCompletedError(
                "Required tasks (Occlusal Evaluation and IQC Holes Detection) are not complete."
            )

        # Raise for non-2xx status codes
        self._transport._raise_for_status(response)

        # Parse JSON response
        data = response.json()
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when generating viewer link.")

        return ViewerLink.model_validate(data)

    def _list_cases(self) -> list[Case]:
        response = self._transport.request_json("GET", "/api/v1/base/cases/")
        if not isinstance(response, dict):
            raise ValidationError("Unexpected response from cases list.")
        cases_data = response.get("cases")
        if not isinstance(cases_data, list):
            raise ValidationError("Unexpected response from cases list.")
        return [Case.model_validate(item) for item in cases_data]


def _resolve_file_paths(paths: Iterable[str | Path]) -> tuple[Path, Path]:
    items = [Path(path) for path in paths]
    if len(items) != 2:
        raise ValidationError("Exactly two file paths are required.")

    upper = next((p for p in items if "upper" in p.name.lower()), None)
    lower = next((p for p in items if "lower" in p.name.lower()), None)
    if upper is None or lower is None:
        upper, lower = items[0], items[1]

    if not upper.exists() or not lower.exists():
        raise ValidationError("Upload files must exist on disk.")
    return upper, lower


def _resolve_extension(upper: Path, lower: Path, extension: str | None) -> str | None:
    normalized = _normalize_extension(extension)
    if normalized:
        _ensure_extension_matches_paths(upper, lower, normalized)
        return normalized if normalized == "drc" else None

    upper_suffix = upper.suffix.lower().lstrip(".")
    lower_suffix = lower.suffix.lower().lstrip(".")
    if upper_suffix != lower_suffix:
        raise ValidationError("Both files must share the same extension.")
    if upper_suffix not in {"stl", "drc"}:
        raise ValidationError("Unsupported file extension.")
    return "drc" if upper_suffix == "drc" else None


def _resolve_file_urls(urls: Iterable[str]) -> tuple[str, str]:
    items = [str(url) for url in urls]
    if len(items) != 2:
        raise ValidationError("Exactly two file URLs are required.")

    for url in items:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("File URLs must be valid http(s) URLs.")

    def _label(value: str) -> str:
        parsed = urlparse(value)
        return Path(parsed.path).name.lower()

    upper = next((u for u in items if "upper" in _label(u)), None)
    lower = next((u for u in items if "lower" in _label(u)), None)
    if upper is None or lower is None:
        upper, lower = items[0], items[1]

    return upper, lower


def _resolve_url_extension(
    upper_url: str,
    lower_url: str,
    extension: str | None,
) -> str | None:
    normalized = _normalize_extension(extension)
    if normalized:
        _ensure_extension_matches_urls(upper_url, lower_url, normalized)
        return normalized if normalized == "drc" else None

    upper_suffix = Path(urlparse(upper_url).path).suffix.lower().lstrip(".")
    lower_suffix = Path(urlparse(lower_url).path).suffix.lower().lstrip(".")
    if upper_suffix != lower_suffix:
        raise ValidationError("Both files must share the same extension.")
    if upper_suffix not in {"stl", "drc"}:
        raise ValidationError("Unsupported file extension.")
    return "drc" if upper_suffix == "drc" else None


def _validate_presigned_url(url: str) -> None:
    """Validate that presigned URL domain is allowed."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Check if domain matches allowed suffixes (both base domain and subdomains)
    # E.g., "storage.googleapis.com" or "bucket.storage.googleapis.com"
    allowed = any(
        domain == suffix.lstrip(".") or domain.endswith(suffix)
        for suffix in ALLOWED_STORAGE_DOMAIN_SUFFIXES
    )

    if not allowed:
        raise ValidationError(
            f"Presigned URL domain not allowed: {domain}. "
            f"Expected domain ending with one of: {', '.join(ALLOWED_STORAGE_DOMAIN_SUFFIXES)}"
        )


def _upload_presigned(url: str, path: Path, timeout_s: float | None) -> None:
    _validate_presigned_url(url)

    with path.open("rb") as handle, httpx.Client(
        timeout=timeout_s or 60.0,
    ) as client:
        headers = {"Content-Length": str(path.stat().st_size)}
        response = client.put(
            url,
            content=iter(lambda: handle.read(8192), b""),
            headers=headers,
        )
    if response.status_code < 200 or response.status_code >= 300:
        raise ValidationError("File upload failed.")


def _normalize_extension(extension: str | None) -> str | None:
    if extension is None:
        return None
    normalized = extension.strip().lower()
    if normalized not in {"stl", "drc"}:
        raise ValidationError("extension must be 'stl' or 'drc'.")
    return normalized


def _ensure_extension_matches_paths(
    upper: Path,
    lower: Path,
    extension: str,
) -> None:
    upper_suffix = upper.suffix.lower().lstrip(".")
    lower_suffix = lower.suffix.lower().lstrip(".")
    if upper_suffix != extension or lower_suffix != extension:
        raise ValidationError("File extension does not match expected format.")


def _ensure_extension_matches_urls(
    upper_url: str,
    lower_url: str,
    extension: str,
) -> None:
    upper_suffix = Path(urlparse(upper_url).path).suffix.lower().lstrip(".")
    lower_suffix = Path(urlparse(lower_url).path).suffix.lower().lstrip(".")
    if upper_suffix and upper_suffix != extension:
        raise ValidationError("File extension does not match expected format.")
    if lower_suffix and lower_suffix != extension:
        raise ValidationError("File extension does not match expected format.")


def _resolve_file_type_from_paths(
    upper: Path,
    lower: Path,
    extension: str | None,
) -> str:
    normalized = _normalize_extension(extension)
    if normalized:
        return normalized
    upper_suffix = upper.suffix.lower().lstrip(".")
    lower_suffix = lower.suffix.lower().lstrip(".")
    if upper_suffix != lower_suffix:
        raise ValidationError("Both files must share the same extension.")
    if upper_suffix not in {"stl", "drc"}:
        raise ValidationError("Unsupported file extension.")
    return upper_suffix


def _resolve_file_type_from_urls(
    upper_url: str,
    lower_url: str,
    extension: str | None,
) -> str:
    normalized = _normalize_extension(extension)
    if normalized:
        return normalized
    upper_suffix = Path(urlparse(upper_url).path).suffix.lower().lstrip(".")
    lower_suffix = Path(urlparse(lower_url).path).suffix.lower().lstrip(".")
    if upper_suffix != lower_suffix:
        raise ValidationError("Both files must share the same extension.")
    if upper_suffix not in {"stl", "drc"}:
        raise ValidationError("Unsupported file extension.")
    return upper_suffix


def _download_url_to_path(
    url: str,
    directory: Path,
    file_type: str,
    label: str,
    timeout_s: float | None,
) -> Path:
    name = Path(urlparse(url).path).name

    # Validate filename to prevent path traversal
    if not name or ".." in name or "/" in name or "\\" in name:
        name = f"{label}.{file_type}"
    elif "." not in name:
        name = f"{label}.{file_type}"
    else:
        suffix = Path(name).suffix.lower().lstrip(".")
        if suffix != file_type:
            name = f"{Path(name).stem}.{file_type}"

    destination = directory / name

    timeout = timeout_s or 60.0
    try:
        with httpx.stream("GET", url, timeout=timeout) as response:
            if response.status_code < 200 or response.status_code >= 300:
                raise ValidationError("File download failed.")
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    size = int(content_length)
                except ValueError:
                    size = None
                if size is not None and size > MAX_URL_DOWNLOAD_BYTES:
                    raise ValidationError("File exceeds maximum size limit.")
            with destination.open("wb") as handle:
                downloaded = 0
                for chunk in response.iter_bytes():
                    downloaded += len(chunk)
                    if downloaded > MAX_URL_DOWNLOAD_BYTES:
                        raise ValidationError("File exceeds maximum size limit.")
                    handle.write(chunk)
    except httpx.RequestError as exc:
        raise ValidationError("File download failed.") from exc

    return destination


def _validate_file_pair(upper: Path, lower: Path, file_type: str) -> None:
    _ensure_not_empty(upper)
    _ensure_not_empty(lower)
    _ensure_not_equal(upper, lower)
    if file_type == "stl":
        _validate_stl_format(upper)
        _validate_stl_format(lower)
    elif file_type == "drc":
        _validate_drc_format(upper)
        _validate_drc_format(lower)
    else:
        raise ValidationError("Unsupported file extension.")


def _ensure_not_empty(path: Path) -> None:
    if path.stat().st_size == 0:
        raise ValidationError("File is empty.")


def _ensure_not_equal(upper: Path, lower: Path) -> None:
    upper_hash = _file_hash(upper)
    lower_hash = _file_hash(lower)
    if upper_hash == lower_hash:
        raise ValidationError("Files are identical.")


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_stl_format(path: Path) -> None:
    if path.suffix.lower() != ".stl":
        raise ValidationError("File does not have .stl extension.")

    np, trimesh = _load_stl_dependencies()
    try:
        mesh = trimesh.load(path, file_type="stl", force="mesh")
    except Exception as exc:
        raise ValidationError("Invalid STL format.") from exc

    if mesh is None:
        raise ValidationError("Invalid STL format.")
    if not hasattr(mesh, "vertices") or mesh.vertices is None:
        raise ValidationError("Invalid STL format.")
    if not hasattr(mesh, "faces") or mesh.faces is None:
        raise ValidationError("Invalid STL format.")
    if len(mesh.vertices) < 3:
        raise ValidationError("Invalid STL format.")
    if len(mesh.faces) < 1:
        raise ValidationError("Invalid STL format.")

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if np.any(np.isnan(vertices)) or np.any(np.isinf(vertices)):
        raise ValidationError("Invalid STL format.")
    if faces.size:
        max_index = len(vertices) - 1
        if np.any(faces < 0) or np.any(faces > max_index):
            raise ValidationError("Invalid STL format.")


def _validate_drc_format(path: Path) -> None:
    if path.suffix.lower() != ".drc":
        raise ValidationError("File does not have .drc extension.")
    DracoPy = _load_drc_dependency()
    np = _load_numpy_dependency()
    try:
        with path.open("rb") as handle:
            decoded = DracoPy.decode(handle.read())
    except Exception as exc:
        raise ValidationError("Invalid DRC format.") from exc

    vertices = None
    faces = None
    if isinstance(decoded, dict):
        vertices = _first_non_none(decoded.get("points"), decoded.get("vertices"))
        faces = _first_non_none(decoded.get("faces"), decoded.get("triangles"))
    else:
        vertices = _first_non_none(
            getattr(decoded, "points", None),
            getattr(decoded, "vertices", None),
        )
        faces = _first_non_none(
            getattr(decoded, "faces", None),
            getattr(decoded, "triangles", None),
        )

    if vertices is None:
        raise ValidationError("Invalid DRC format.")
    vertices = np.asarray(vertices)
    if vertices.size < 3:
        raise ValidationError("Invalid DRC format.")
    if faces is not None:
        faces = np.asarray(faces)
        if faces.size == 0:
            raise ValidationError("Invalid DRC format.")


def _first_non_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _load_stl_dependencies():
    try:
        import numpy as np
        import trimesh
    except Exception as exc:
        raise ValidationError(
            "STL validation requires numpy and trimesh to be installed."
        ) from exc
    return np, trimesh


def _load_numpy_dependency():
    try:
        import numpy as np
    except Exception as exc:
        raise ValidationError("DRC validation requires numpy to be installed.") from exc
    return np


def _load_drc_dependency():
    try:
        import DracoPy
    except Exception as exc:
        raise ValidationError(
            "DRC validation requires DracoPy to be installed."
        ) from exc
    return DracoPy
