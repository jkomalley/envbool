"""Exception hierarchy for envbool.

All exceptions inherit from EnvBoolError so callers can catch the entire
library with a single except clause. Where it makes sense, exceptions also
inherit from a standard Python exception (ValueError, etc.) so that code
which predates envbool adoption keeps working without changes.

Hierarchy:
    EnvBoolError(Exception)
        InvalidBoolValueError(EnvBoolError, ValueError)
        ConflictingValuesError(EnvBoolError, ValueError)
        MissingEnvVarError(EnvBoolError, KeyError)
"""


class EnvBoolError(Exception):
    """Base exception for all envbool errors.

    Catch this to handle any error from the library in one place.
    """


class InvalidBoolValueError(EnvBoolError, ValueError):
    """Raised in strict mode when a value is not in the truthy or falsy sets.

    Dual inheritance lets existing except ValueError handlers keep working
    after a codebase adopts envbool, with no migration required.
    """

    # Attributes are set by the raising code after construction rather than in
    # __init__ to keep the signature simple and avoid pickling/subclassing issues.

    # Name of the environment variable, if the error originated from envbool().
    # None when raised directly from to_bool() with no env var context.
    var: str | None

    # The normalized (stripped, lowercased) value that was not recognized.
    value: str

    # The effective truthy and falsy sets at the time of the error. Attached
    # so callers can inspect exactly what was expected without re-running resolution.
    truthy: frozenset[str]
    falsy: frozenset[str]


class ConflictingValuesError(EnvBoolError, ValueError):
    """Raised in strict mode when the effective truthy and falsy sets overlap.

    This is a configuration error, not a bad input value -- which is why it is
    distinct from InvalidBoolValueError. It is raised on every strict call while
    the conflict exists (not only when the value lands in the overlap), so a
    misconfiguration fails immediately instead of waiting for a colliding token.
    ValueError inheritance matches InvalidBoolValueError, so a single
    ``except ValueError`` still covers every strict-mode failure.
    """

    # Set by the raising code after construction (see InvalidBoolValueError for
    # why attributes live here rather than in __init__).

    # Values present in both sets.
    overlap: frozenset[str]

    # The effective truthy and falsy sets that conflicted.
    truthy: frozenset[str]
    falsy: frozenset[str]


class MissingEnvVarError(EnvBoolError, KeyError):
    """Raised by envbool(var, required=True) when var is not set in the environment.

    Dual inheritance with KeyError mirrors the InvalidBoolValueError(ValueError)
    pattern: a missing os.environ lookup naturally raises KeyError, so existing
    ``except KeyError`` handlers keep working after a codebase adopts envbool.

    Only a truly-unset variable triggers this -- a variable set to an empty
    string is "present" and coerces normally via the caller's default.
    """

    # KeyError.__str__ reprs its argument (e.g. `str(KeyError("x"))` == `"'x'"`),
    # which would wrap every rendered message in stray quotes. Restore plain
    # Exception formatting so `str(e)` and CLI/log output read cleanly.
    __str__ = Exception.__str__

    # Set by the raising code after construction (see InvalidBoolValueError for
    # why attributes live here rather than in __init__).

    # Name of the environment variable that was required but not set.
    var: str
