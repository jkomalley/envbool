"""Exception hierarchy for envbool.

All exceptions inherit from EnvBoolError so callers can catch the entire
library with a single except clause. Where it makes sense, exceptions also
inherit from a standard Python exception (ValueError, etc.) so that code
which predates envbool adoption keeps working without changes.

Hierarchy:
    EnvBoolError(Exception)
        InvalidBoolValueError(EnvBoolError, ValueError)
        ConfigError(EnvBoolError)
"""

from pathlib import Path


class EnvBoolError(Exception):
    """Base exception for all envbool errors.

    Catch this to handle any error from the library in one place.
    """


class InvalidBoolValueError(EnvBoolError, ValueError):
    """Raised in strict mode when a value is not in the truthy or falsy sets.

    Dual inheritance lets existing except ValueError handlers keep working
    after a codebase adopts envbool, with no migration required.

    Attributes are set by the raising code (to_bool / envbool) after
    construction rather than in __init__, keeping the signature simple and
    avoiding issues with pickling or subclassing.
    """

    # Name of the environment variable, if the error originated from envbool().
    # None when raised directly from to_bool() with no env var context.
    var: str | None

    # The normalized (stripped, lowercased) value that was not recognized.
    value: str

    # The effective truthy and falsy sets at the time of the error. Attached
    # so callers can inspect exactly what was expected without re-running resolution.
    truthy: frozenset[str]
    falsy: frozenset[str]


class ConfigError(EnvBoolError):
    """Raised when a config file is malformed or contains invalid values.

    Not a ValueError -- config problems are distinct from bad boolean values
    and should not be caught by generic except ValueError handlers.
    """

    # Path to the config file that caused the error, for diagnostic messages.
    path: Path
