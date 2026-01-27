"""Task resources."""

from __future__ import annotations

import time

from movix_qc_sdk.errors import MovixQCError, ValidationError
from movix_qc_sdk.models import Task, TaskStatus
from movix_qc_sdk.transport import Transport


class TasksClient:
    """Client for task-related operations."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def get(self, task_id: int, case_id: str | None = None) -> Task:
        """Get a task by ID."""

        if not case_id:
            raise ValidationError("case_id is required to fetch a task.")
        data = self._transport.request_json(
            "GET",
            f"/api/v1/services/cases/{case_id}/tasks/{task_id}",
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when fetching task.")
        return Task.from_api(data)

    def list(
        self,
        case_id: str,
        status: TaskStatus | str | None = None,
    ) -> list[Task]:
        """List tasks for a case."""

        data = self._transport.request_json(
            "GET",
            f"/api/v1/services/cases/{case_id}/tasks/",
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when listing tasks.")
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise ValidationError("Unexpected response when listing tasks.")

        parsed = [Task.from_api(item) for item in tasks if isinstance(item, dict)]
        normalized_status = _normalize_status_filter(status)
        if normalized_status is None:
            return parsed
        return [task for task in parsed if task.status == normalized_status]

    def wait(
        self,
        task_id: int,
        case_id: str | None = None,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
    ) -> Task:
        """Poll a task until it completes or times out."""

        if timeout_s <= 0:
            raise ValidationError("timeout_s must be greater than zero.")
        if poll_interval_s <= 0:
            raise ValidationError("poll_interval_s must be greater than zero.")

        deadline = time.monotonic() + timeout_s
        max_iterations = int(timeout_s / poll_interval_s) + 10  # +10 buffer for safety

        iteration = 0
        while iteration < max_iterations:
            task = self.get(task_id=task_id, case_id=case_id)
            if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                return task
            if time.monotonic() >= deadline:
                raise MovixQCError("Timed out waiting for task completion.")
            time.sleep(poll_interval_s)
            iteration += 1

        raise MovixQCError("Timed out waiting for task completion.")


def _normalize_status_filter(status: TaskStatus | str | None) -> TaskStatus | None:
    if status is None:
        return None
    if isinstance(status, TaskStatus):
        return status
    status_value = str(status).strip().lower()
    for item in TaskStatus:
        if item.value == status_value:
            return item
    raise ValidationError("Unknown task status filter.")
