"""SDK error types."""

from __future__ import annotations


class MovixQCError(Exception):
    """Base error for the Movix QC SDK."""


class ValidationError(MovixQCError):
    """Raised when SDK input validation fails."""


class AuthenticationError(MovixQCError):
    """Raised when authentication fails."""


class AuthorizationError(MovixQCError):
    """Raised when authorization fails."""


class NotFoundError(MovixQCError):
    """Raised when a resource is not found."""


class RateLimitError(MovixQCError):
    """Raised when the API rate limits the request."""


class ApiError(MovixQCError):
    """Raised for generic API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TasksNotCompletedError(MovixQCError):
    """Raised when required tasks are not completed for the operation."""
