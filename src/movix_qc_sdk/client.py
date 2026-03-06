"""Top-level SDK client."""

from __future__ import annotations

from movix_qc_sdk.auth import PasswordTokenProvider, TokenProvider
from movix_qc_sdk.cases import CasesClient
from movix_qc_sdk.config import Config, resolve_config
from movix_qc_sdk.errors import ValidationError
from movix_qc_sdk.tasks import TasksClient
from movix_qc_sdk.transport import Transport


class Client:
    """Client for the Movix QC API."""

    def __init__(
        self,
        *,
        api_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        user_agent: str | None = None,
        occlusion_threshold_mm: float | None = None,
        occlusion_threshold_gap_mm: float | None = None,
        holes_threshold_area_mm: float | None = None,
        token_provider: TokenProvider | None = None,
    ) -> None:
        config = resolve_config(
            api_url,
            username,
            password,
            timeout,
            retries,
            user_agent,
            occlusion_threshold_mm,
            occlusion_threshold_gap_mm,
            holes_threshold_area_mm,
        )
        self._config = config

        if token_provider is None:
            if not config.username or not config.password:
                raise ValidationError("username and password are required.")
            token_provider = PasswordTokenProvider(
                api_url=config.api_url,
                username=config.username,
                password=config.password,
                timeout_s=config.timeout_s,
                user_agent=config.user_agent,
            )

        self._token_provider = token_provider
        self._transport = Transport(
            api_url=config.api_url,
            timeout_s=config.timeout_s,
            retries=config.retries,
            user_agent=config.user_agent,
            token_provider=token_provider,
        )
        self.cases = CasesClient(self._transport)
        self.tasks = TasksClient(self._transport, config)

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Close underlying HTTP connections."""

        self._transport.close()
        if isinstance(self._token_provider, PasswordTokenProvider):
            self._token_provider.close()

    def health(self) -> bool:
        """Check API connectivity with an authenticated request."""

        try:
            response = self._transport.request("GET", "/api/v1/auth/profile/")
            if not (200 <= response.status_code < 300):
                return False

            # Validate response structure
            try:
                data = response.json()
                return isinstance(data, dict) and "email" in data
            except Exception:
                return False
        except Exception:
            return False

    @property
    def config(self) -> Config:
        """Return resolved configuration."""

        return self._config
