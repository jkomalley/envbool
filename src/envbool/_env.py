"""envbool() -- read an environment variable and coerce it to bool.

Public surface:
    envbool()  -- the primary library API
"""
# This is the only layer in the package that touches os.environ. The split
# between _env.py and _core.py keeps os.environ access isolated here so that
# to_bool() can be tested without monkeypatching the environment.
# Delegation chain: envbool() -> to_bool() -> _resolve() (+ _get_config())

__all__ = ["envbool"]

import os
from collections.abc import Iterable

from envbool._core import to_bool


def envbool(
    var: str,
    *,
    default: bool = False,
    strict: bool | None = None,
    warn: bool | None = None,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> bool:
    """Read an environment variable and coerce its value to bool.

    Args:
        var: Environment variable name.
        default: Returned when the variable is unset or empty.
        strict: Raise on unrecognized values. None defers to config (default False).
        warn: Log a warning on unrecognized values. None defers to config
            (default False).
        truthy: Replaces the effective truthy set.
        falsy: Replaces the effective falsy set.
        extend_truthy: Extends the effective truthy set.
        extend_falsy: Extends the effective falsy set.

    Returns:
        True if the env var value is in the truthy set, False otherwise.

    Raises:
        InvalidBoolValueError: In strict mode when the value is unrecognized.
    """
    # Missing var becomes "" so to_bool treats it the same as an empty value,
    # returning `default` rather than raising or treating absence as a distinct state.
    value = os.environ.get(var, "")
    # _var=var threads the env var name into any InvalidBoolValueError so the message
    # reads "Invalid boolean value for DEBUG: 'maybe'" instead of just the value.
    # It is a private parameter to keep it out of to_bool()'s public signature.
    return to_bool(
        value,
        default=default,
        strict=strict,
        warn=warn,
        truthy=truthy,
        falsy=falsy,
        extend_truthy=extend_truthy,
        extend_falsy=extend_falsy,
        _var=var,
    )
