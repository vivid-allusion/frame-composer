"""Custom exceptions for fail-fast error handling."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""


class ValidationError(Exception):
    """Raised when input validation fails."""


class PreflightExit(Exception):
    """Raised to signal an early exit from preflight checks."""

    def __init__(self, exit_code: int = 0):
        self.exit_code = exit_code
        super().__init__(f"Preflight exit with code {exit_code}")
