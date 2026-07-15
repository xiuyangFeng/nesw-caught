from __future__ import annotations


class XMonitorError(ValueError):
    """Base domain error for the X monitor feature (maps to HTTP 400 by default)."""


class XMonitorDisabledError(XMonitorError):
    """Raised when the feature flag is off (maps to HTTP 503)."""


class XAccountNotFoundError(XMonitorError):
    """Raised when a tracked account does not exist (maps to HTTP 404)."""


class XAccountAlreadyExistsError(XMonitorError):
    """Raised when creating a tracked account that already exists (maps to HTTP 409)."""
