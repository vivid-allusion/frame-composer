"""Custom exceptions for fail-fast error handling."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""


class ValidationError(Exception):
    """Raised when input validation fails."""
