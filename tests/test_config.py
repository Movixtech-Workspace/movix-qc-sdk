import pytest

from movix_qc_sdk.config import resolve_config
from movix_qc_sdk.errors import ValidationError


def test_resolve_config_from_env(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com/")
    monkeypatch.setenv("MOVIX_QC_USERNAME", "user")
    monkeypatch.setenv("MOVIX_QC_PASSWORD", "pass")
    monkeypatch.setenv("MOVIX_QC_TIMEOUT", "15")
    monkeypatch.setenv("MOVIX_QC_RETRIES", "2")
    monkeypatch.setenv("MOVIX_QC_USER_AGENT", "custom")

    config = resolve_config(None, None, None, None, None, None, None, None, None)
    assert config.api_url == "https://api.example.com"
    assert config.username == "user"
    assert config.password == "pass"
    assert config.timeout_s == 15.0
    assert config.retries == 2
    assert config.user_agent == "custom"


def test_resolve_config_defaults(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com/")
    monkeypatch.delenv("MOVIX_QC_USERNAME", raising=False)
    monkeypatch.delenv("MOVIX_QC_PASSWORD", raising=False)
    monkeypatch.delenv("MOVIX_QC_TIMEOUT", raising=False)
    monkeypatch.delenv("MOVIX_QC_RETRIES", raising=False)
    monkeypatch.delenv("MOVIX_QC_USER_AGENT", raising=False)

    config = resolve_config(None, None, None, None, None, None, None, None, None)
    assert config.api_url == "https://api.example.com"
    assert config.username is None
    assert config.password is None
    assert config.timeout_s == 45.0
    assert config.retries == 10
    assert config.user_agent == "movix-qc-sdk/0.3.0"


def test_resolve_config_api_url_validation(monkeypatch):
    # Missing api_url
    monkeypatch.delenv("MOVIX_QC_API_URL", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        resolve_config(None, None, None, None, None, None, None, None, None)
    assert "api_url is required" in str(excinfo.value)

    # Invalid protocol (not http/https)
    monkeypatch.setenv("MOVIX_QC_API_URL", "ftp://api.example.com")
    with pytest.raises(ValidationError) as excinfo:
        resolve_config(None, None, None, None, None, None, None, None, None)
    assert "valid http(s) URL" in str(excinfo.value)


def test_resolve_config_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    monkeypatch.setenv("MOVIX_QC_TIMEOUT", "nope")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, None, None, None)


def test_resolve_config_rejects_non_positive_timeout(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    monkeypatch.setenv("MOVIX_QC_TIMEOUT", "0")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, None, None, None)


def test_resolve_config_rejects_invalid_retries(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    monkeypatch.setenv("MOVIX_QC_RETRIES", "bad")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, None, None, None)


def test_resolve_config_rejects_negative_retries(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    monkeypatch.setenv("MOVIX_QC_RETRIES", "-1")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, None, None, None)


def test_resolve_config_threshold_defaults(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com/")
    config = resolve_config(None, None, None, None, None, None, None, None, None)
    assert config.occlusion_threshold_mm == 0.0
    assert config.occlusion_threshold_gap_mm == 0.0
    assert config.holes_threshold_area_mm == 0.0


def test_resolve_config_threshold_from_env(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com/")
    monkeypatch.setenv("MOVIX_QC_OCCLUSION_THRESHOLD_MM", "0.3")
    monkeypatch.setenv("MOVIX_QC_OCCLUSION_THRESHOLD_GAP_MM", "0.15")
    monkeypatch.setenv("MOVIX_QC_HOLES_THRESHOLD_AREA_MM", "15.0")
    config = resolve_config(None, None, None, None, None, None, None, None, None)
    assert config.occlusion_threshold_mm == 0.3
    assert config.occlusion_threshold_gap_mm == 0.15
    assert config.holes_threshold_area_mm == 15.0


def test_resolve_config_threshold_from_args(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com/")
    config = resolve_config(None, None, None, None, None, None, 0.5, 0.2, 20.0)
    assert config.occlusion_threshold_mm == 0.5
    assert config.occlusion_threshold_gap_mm == 0.2
    assert config.holes_threshold_area_mm == 20.0


def test_resolve_config_rejects_negative_thresholds(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, -0.1, None, None)


def test_resolve_config_rejects_negative_gap_threshold(monkeypatch):
    monkeypatch.setenv("MOVIX_QC_API_URL", "https://api.example.com")
    with pytest.raises(ValidationError):
        resolve_config(None, None, None, None, None, None, None, -0.1, None)
