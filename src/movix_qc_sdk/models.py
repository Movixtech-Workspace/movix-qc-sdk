"""SDK models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Normalized task status values."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_STATUS_MAP = {
    "created": TaskStatus.QUEUED,
    "run": TaskStatus.RUNNING,
    "done": TaskStatus.SUCCEEDED,
    "failed": TaskStatus.FAILED,
    "error": TaskStatus.FAILED,
}


def normalize_task_status(value: str | None) -> TaskStatus | None:
    """Normalize API status strings into SDK status values."""

    if value is None:
        return None
    status = _STATUS_MAP.get(value.strip().lower())
    return status


class Case(BaseModel):
    """Case model."""

    model_config = ConfigDict(extra="ignore")

    case_id: str = Field(alias="case_id")
    created_at: datetime | None = None
    updated_at: datetime | None = None
    note: str | None = None
    client: str | None = None


class Task(BaseModel):
    """Task model."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    title: str | None = None
    description: str | None = None
    service_name: str | None = None
    status: TaskStatus | None = None
    started: datetime | None = None
    completed: datetime | None = None
    created: datetime | None = None
    result: Any | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Task":
        normalized = dict(payload)
        # Normalize status
        normalized["status"] = normalize_task_status(payload.get("status"))
        # Normalize task_id field (API uses both "id" and "task_id")
        if "id" in payload and "task_id" not in payload:
            normalized["task_id"] = payload["id"]
        return cls.model_validate(normalized)


class UploadResult(BaseModel):
    """Result of uploading files to a case."""

    model_config = ConfigDict(extra="ignore")

    case_id: str
    upper_file_id: str
    lower_file_id: str


class SummaryResult(BaseModel):
    """Result of generating a case summary."""

    model_config = ConfigDict(extra="ignore")

    message: str | None


class ViewerLink(BaseModel):
    """Viewer link for a case."""

    model_config = ConfigDict(extra="ignore")

    url: str
    public_id: str
    expires_at: datetime
