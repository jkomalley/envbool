"""Pure string-to-bool coercion with configurable truthy/falsy sets.

Public surface:
    DEFAULT_TRUTHY  -- the built-in truthy set
    DEFAULT_FALSY   -- the built-in falsy set
    to_bool()       -- coerce a single string to bool

Private surface (used by _env.py and tests):
    _resolve()      -- compute effective truthy/falsy sets from call-site args
"""
# This module has no knowledge of os.environ -- that lives in _env.py. It also
# holds no process-wide state: every setting comes from the call-site
# arguments, so callers that want a fixed policy bind it with functools.partial.

__all__ = ["to_bool"]

import logging
from collections.abc import Iterable

from envbool.exceptions import ConflictingValuesError, InvalidBoolValueError

# Module-level logger -- attributed to "envbool._core" so callers can filter it
# independently from "envbool.config" or the root "envbool" logger.
_logger = logging.getLogger(__name__)

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})


def _normalize_set(values: Iterable[str]) -> frozenset[str]:
    """Strip and lowercase values so they match to_bool()'s normalized input."""
    return frozenset(v.strip().lower() for v in values)


def _apply_replace_then_extend(
    base: frozenset[str],
    replace: Iterable[str] | None,
    extend: Iterable[str] | None,
) -> frozenset[str]:
    """Resolve a value set: replace the base (if given), then extend the result.

    Used by _resolve() for each of the truthy and falsy sets:
        replace -- swaps out base entirely; the caller owns the starting set
        extend  -- additive; merged on top of whatever replace left
        neither -- use base as-is
    Passing both applies replace first, then extend, so neither argument is
    silently dropped.

    Args:
        base: The starting set, used when replace is None.
        replace: If not None, fully replaces base (normalized).
        extend: If not None, merged on top of the (possibly replaced) set.

    Returns:
        The resolved, normalized frozenset.
    """
    result = _normalize_set(replace) if replace is not None else base
    if extend is not None:
        result |= _normalize_set(extend)
    return result


# Public API


def to_bool(
    value: str,
    *,
    default: bool = False,
    strict: bool = False,
    warn: bool = False,
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
        strict: Raise on unrecognized values.
        warn: Log a warning on unrecognized values.
        truthy: Replaces the effective truthy set.
        falsy: Replaces the effective falsy set.
        extend_truthy: Extends the effective truthy set, after any truthy
            replacement.
        extend_falsy: Extends the effective falsy set, after any falsy
            replacement.
        _var: Internal - env var name for error messages when called via envbool().

    Returns:
        True if value is in the truthy set, False otherwise.

    Raises:
        InvalidBoolValueError: In strict mode when value is unrecognized.
        ConflictingValuesError: In strict mode when the effective truthy and
            falsy sets overlap.
    """
    # Normalize first so all comparisons are case- and whitespace-insensitive.
    # Empty after normalization means "unset" -- return the caller's default
    # rather than treating it as an unrecognized value.
    normalized = value.strip().lower()
    if not normalized:
        return default

    # Precedence is two-level: the built-in sets, then the call-site args
    # (truthy/extend_truthy/falsy/extend_falsy) layered on top by _resolve.
    effective_truthy, effective_falsy = _resolve(
        truthy=truthy,
        falsy=falsy,
        extend_truthy=extend_truthy,
        extend_falsy=extend_falsy,
    )

    # Overlapping sets are a configuration mistake. Strict mode promises every
    # accepted value is unambiguous, so it rejects the configuration outright --
    # on every call, not just when the value lands in the overlap, so the
    # mistake surfaces at the first strict read. Lenient mode warns so the
    # problem is visible, then lets truthy win to stay predictable.
    overlap = effective_truthy & effective_falsy
    if overlap:
        if strict:
            err = ConflictingValuesError(
                f"Truthy and falsy sets overlap: {', '.join(sorted(overlap))}"
            )
            err.overlap = overlap
            err.truthy = effective_truthy
            err.falsy = effective_falsy
            raise err
        _logger.warning(
            "Overlapping truthy/falsy values (truthy wins): %s", sorted(overlap)
        )

    if normalized in effective_truthy:
        return True

    # Falsy is checked after truthy so the lenient overlap rule above (truthy
    # wins) is enforced without any extra branching.
    if normalized in effective_falsy:
        return False

    if strict:
        truthy_list = ", ".join(sorted(effective_truthy))
        falsy_list = ", ".join(sorted(effective_falsy))
        # _var is threaded in by envbool() so the error message names the env
        # var; it's a private param to keep it out of the public to_bool() API.
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

    if warn:
        _logger.warning("Unrecognized boolean value: %r", normalized)

    # Lenient fallback: anything unrecognized is treated as falsy. This matches
    # the "off by default" mental model of environment variable feature flags.
    return False


# Private API


def _resolve(
    *,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    # Replace-then-extend, per set -- see the _apply_replace_then_extend()
    # docstring for the full precedence rules.
    effective_truthy = _apply_replace_then_extend(DEFAULT_TRUTHY, truthy, extend_truthy)
    effective_falsy = _apply_replace_then_extend(DEFAULT_FALSY, falsy, extend_falsy)

    return (effective_truthy, effective_falsy)
