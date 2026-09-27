"""Pure string-to-bool coercion with configurable truthy/falsy sets.

Public surface:
    DEFAULT_TRUTHY  -- the built-in truthy set (from _defaults)
    DEFAULT_FALSY   -- the built-in falsy set (from _defaults)
    to_bool()       -- coerce a single string to bool

Private surface (used by _env.py and tests):
    _resolve()      -- compute effective truthy/falsy sets from layered inputs
"""
# This module has no knowledge of os.environ -- that lives in _env.py. It does
# consult get_defaults() from _defaults.py so that strict=None/warn=None defer
# to the process-level defaults (set_defaults()) rather than always defaulting
# to False.

__all__ = ["to_bool"]

import logging
from collections.abc import Iterable

from envbool._defaults import (
    DEFAULT_FALSY,
    DEFAULT_TRUTHY,
    _apply_replace_then_extend,
    get_defaults,
)
from envbool.exceptions import ConflictingValuesError, InvalidBoolValueError

# Module-level logger -- attributed to "envbool._core" so callers can filter it
# independently from "envbool.config" or the root "envbool" logger.
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
        strict: Raise on unrecognized values. None defers to process-level
            defaults (set_defaults()) (default False).
        warn: Log a warning on unrecognized values. None defers to
            process-level defaults (set_defaults()) (default False).
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

    # Read the process-level defaults (set once via set_defaults(), or the
    # built-ins if never called). _resolve then applies the full three-level
    # precedence chain:
    #   hardcoded defaults (_defaults.py)
    #   -> process-level defaults (effective_truthy/effective_falsy already
    #      resolved there by set_defaults())
    #   -> call-site args (truthy/extend_truthy/falsy/extend_falsy)
    defaults = get_defaults()
    effective_truthy, effective_falsy = _resolve(
        config_truthy=defaults.effective_truthy,
        config_falsy=defaults.effective_falsy,
        truthy=truthy,
        falsy=falsy,
        extend_truthy=extend_truthy,
        extend_falsy=extend_falsy,
    )

    # Three-state logic: True/False at the call site override the process-level
    # default; None defers to whatever set_defaults() last set (which defaults
    # to False if set_defaults() was never called). Resolved before the lookup
    # because the overlap check below also depends on it.
    effective_strict = strict if strict is not None else defaults.strict

    # Overlapping sets are a configuration mistake. Strict mode promises every
    # accepted value is unambiguous, so it rejects the configuration outright --
    # on every call, not just when the value lands in the overlap, so the
    # mistake surfaces at the first strict read. Lenient mode warns so the
    # problem is visible, then lets truthy win to stay predictable.
    overlap = effective_truthy & effective_falsy
    if overlap:
        if effective_strict:
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

    if effective_strict:
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

    effective_warn = warn if warn is not None else defaults.warn
    if effective_warn:
        _logger.warning("Unrecognized boolean value: %r", normalized)

    # Lenient fallback: anything unrecognized is treated as falsy. This matches
    # the "off by default" mental model of environment variable feature flags.
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
    # Replace-then-extend, per set -- see the _apply_replace_then_extend()
    # docstring for the full precedence rules.
    effective_truthy = _apply_replace_then_extend(config_truthy, truthy, extend_truthy)
    effective_falsy = _apply_replace_then_extend(config_falsy, falsy, extend_falsy)

    return (effective_truthy, effective_falsy)
