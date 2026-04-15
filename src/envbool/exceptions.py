"""Custom exception hierarchy for envbool."""

from pathlib import Path


class EnvBoolError(Exception):
    """Base exception for all envbool errors."""


class InvalidBoolValueError(EnvBoolError, ValueError):
    """Raised in strict mode when a value isn't in the truthy or falsy sets.

    Inherits from both EnvBoolError and ValueError so that existing
    code catching ValueError still works.
    """

    var: str | None  # env var name if from envbool(), None if from to_bool()
    value: str  # the unrecognized value
    truthy: frozenset[str]  # the effective truthy set
    falsy: frozenset[str]  # the effective falsy set


class ConfigError(EnvBoolError):
    """Raised when a config file is malformed or contains invalid values."""

    path: Path  # path to the problematic config file
