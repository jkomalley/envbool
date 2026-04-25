"""Core coercion logic: to_bool, set resolution, default sets."""

import logging
from collections.abc import Iterable

from envbool.exceptions import InvalidBoolValueError

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})

_logger = logging.getLogger(__name__)

# Public API


def to_bool(
    value: str,
    *,
    default: bool = False,
    strict: bool | None = None,
    warn: bool | None = None,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
    _var: str | None = None,
) -> bool:
    """Coerce a string to bool.

    Args:
        value: The string to coerce.
        default: Returned when value is empty or unset.
        strict: Raise on unrecognized values. None defers to config (default False).
        warn: Log a warning on unrecognized values. None defers to config
            (default False).
        truthy: Replaces the effective truthy set.
        falsy: Replaces the effective falsy set.
        extend_truthy: Extends the effective truthy set.
        extend_falsy: Extends the effective falsy set.
        _var: Internal — env var name for error messages when called via envbool().

    Returns:
        True if value is in the truthy set, False otherwise.

    Raises:
        InvalidBoolValueError: In strict mode when value is unrecognized.
    """
    normalized = value.strip().lower()
    if not normalized:
        return default

    effective_truthy, effective_falsy = _resolve(
        truthy=truthy,
        falsy=falsy,
        extend_truthy=extend_truthy,
        extend_falsy=extend_falsy,
    )

    overlap = effective_truthy & effective_falsy
    if overlap:
        _logger.warning(
            "Overlapping truthy/falsy values (truthy wins): %s", sorted(overlap)
        )

    if normalized in effective_truthy:
        return True

    if normalized in effective_falsy:
        return False

    effective_strict = strict if strict is not None else False
    if effective_strict:
        truthy_list = ", ".join(sorted(effective_truthy))
        falsy_list = ", ".join(sorted(effective_falsy))
        if _var is not None:
            msg = (
                f"Invalid boolean value for {_var}: {normalized!r}\n"
                f"  Expected truthy: {truthy_list}\n"
                f"  Expected falsy:  {falsy_list}"
            )
        else:
            msg = (
                f"Invalid boolean value: {normalized!r}\n"
                f"  Expected truthy: {truthy_list}\n"
                f"  Expected falsy:  {falsy_list}"
            )
        err = InvalidBoolValueError(msg)
        err.var = _var
        err.value = normalized
        err.truthy = effective_truthy
        err.falsy = effective_falsy
        raise err

    effective_warn = warn if warn is not None else False
    if effective_warn:
        _logger.warning("Unrecognized boolean value: %r", normalized)

    return False


# Private API


def _resolve(
    *,
    config_truthy: frozenset[str] = DEFAULT_TRUTHY,
    config_falsy: frozenset[str] = DEFAULT_FALSY,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    if truthy is not None:
        effective_truthy = frozenset(truthy)
    elif extend_truthy is not None:
        effective_truthy = config_truthy | frozenset(extend_truthy)
    else:
        effective_truthy = config_truthy

    if falsy is not None:
        effective_falsy = frozenset(falsy)
    elif extend_falsy is not None:
        effective_falsy = config_falsy | frozenset(extend_falsy)
    else:
        effective_falsy = config_falsy

    return (effective_truthy, effective_falsy)
