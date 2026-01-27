from movix_qc_sdk.models import Task, TaskStatus, normalize_task_status


def test_status_normalization():
    assert normalize_task_status("Created") == TaskStatus.QUEUED
    assert normalize_task_status("Run") == TaskStatus.RUNNING
    assert normalize_task_status("Done") == TaskStatus.SUCCEEDED
    assert normalize_task_status("Failed") == TaskStatus.FAILED
    assert normalize_task_status("Error") == TaskStatus.FAILED


def test_task_from_api_normalizes_status():
    task = Task.from_api({"id": 1, "status": "Run"})
    assert task.status == TaskStatus.RUNNING
