"""Task resources."""

from __future__ import annotations

import time

from movix_qc_sdk.config import Config
from movix_qc_sdk.errors import MovixQCError, ValidationError
from movix_qc_sdk.models import Task, TaskStatus
from movix_qc_sdk.transport import Transport


class TasksClient:
    """Client for task-related operations."""

    def __init__(self, transport: Transport, config: Config) -> None:
        self._transport = transport
        self._config = config

    def get(self, task_id: int, case_id: str | None = None) -> Task:
        """Get a task by ID."""

        if not case_id:
            raise ValidationError("case_id is required to fetch a task.")
        data = self._transport.request_json(
            "GET",
            f"/api/v1/services/cases/{case_id}/tasks/{task_id}/",
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

    def create_data_validation(self, case_id: str) -> Task:
        """Create a data validation task (synchronous)."""

        data = self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case_id}/tasks/",
            json_body={"service": "Data Validation"}
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when creating data validation task.")
        return Task.from_api(data)

    def create_occlusion(
        self,
        case_id: str,
        *,
        threshold_mm: float | None = None,
        visualization: bool = True,
        generate_drc: bool = False,
    ) -> Task:
        """Create an occlusal evaluation task.

        Args:
            case_id: The case ID
            threshold_mm: Occlusion threshold in mm (defaults to config value: 0.0mm)
            visualization: Generate visualization assets (default: True)
            generate_drc: Generate DRC files alongside meshes (default: False)

        Returns:
            Task object with task_id and status
        """

        threshold_value = threshold_mm if threshold_mm is not None else self._config.occlusion_threshold_mm

        payload = {
            "threshold_mm": threshold_value,
            "visualization": visualization,
            "generate_drc": generate_drc,
        }

        data = self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case_id}/tasks/hyperocclusion",
            json_body=payload
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when creating occlusion task.")
        return Task.from_api(data)

    def create_holes(
        self,
        case_id: str,
        *,
        threshold_area_mm: float | None = None,
        crown_dilation_mm: float | None = None,
        visualization: bool = True,
        generate_drc: bool = False,
    ) -> Task:
        """Create a holes detection task.

        Args:
            case_id: The case ID
            threshold_area_mm: Minimum hole area in mm² (defaults to config value: 0.0mm²)
            crown_dilation_mm: Crown dilation distance in mm for hole detection (optional)
            visualization: Generate visualization assets (default: True)
            generate_drc: Generate DRC files alongside meshes (default: False)

        Returns:
            Task object with task_id and status
        """

        if crown_dilation_mm is not None and crown_dilation_mm < 0:
            raise ValidationError("crown_dilation_mm must be zero or greater.")

        threshold_value = threshold_area_mm if threshold_area_mm is not None else self._config.holes_threshold_area_mm

        payload: dict[str, object] = {
            "threshold_area_mm": threshold_value,
            "visualization": visualization,
            "generate_drc": generate_drc,
        }

        if crown_dilation_mm is not None:
            payload["crown_dilation_mm"] = crown_dilation_mm

        data = self._transport.request_json(
            "POST",
            f"/api/v1/services/cases/{case_id}/tasks/holes",
            json_body=payload
        )
        if not isinstance(data, dict):
            raise ValidationError("Unexpected response when creating holes task.")
        return Task.from_api(data)

    def wait_for_completion(
        self,
        case_id: str,
        task_id: int,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
    ) -> Task:
        """Wait for a task to complete (alias for wait method)."""

        return self.wait(task_id=task_id, case_id=case_id, timeout_s=timeout_s, poll_interval_s=poll_interval_s)


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
