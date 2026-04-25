"""Pure string-to-bool coercion with configurable truthy/falsy sets.

Public surface:
    DEFAULT_TRUTHY  -- the built-in truthy set (from _defaults)
    DEFAULT_FALSY   -- the built-in falsy set (from _defaults)
    to_bool()       -- coerce a single string to bool

Private surface (used by _env.py and tests):
    _resolve()      -- compute effective truthy/falsy sets from layered inputs
"""
# This module has no knowledge of os.environ -- that lives in _env.py. It does
# consult the config cache (_get_config) so that strict=None/warn=None defer to
# the loaded config file rather than always defaulting to False.
# Import order matters: _config.py imports _defaults (not _core), so _core.py
# can safely import from _config.py without creating a circular dependency.

__all__ = ["to_bool"]

import logging
from collections.abc import Iterable

from envbool._config import _get_config
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY
from envbool.exceptions import InvalidBoolValueError

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
        strict: Raise on unrecognized values. None defers to config (default False).
        warn: Log a warning on unrecognized values. None defers to config
            (default False).
        truthy: Replaces the effective truthy set.
        falsy: Replaces the effective falsy set.
        extend_truthy: Extends the effective truthy set.
        extend_falsy: Extends the effective falsy set.
        _var: Internal - env var name for error messages when called via envbool().

    Returns:
        True if value is in the truthy set, False otherwise.

    Raises:
        InvalidBoolValueError: In strict mode when value is unrecognized.
    """
    # Normalize first so all comparisons are case- and whitespace-insensitive.
    # Empty after normalization means "unset" -- return the caller's default
    # rather than treating it as an unrecognized value.
    normalized = value.strip().lower()
    if not normalized:
        return default

    # Load config once per process (cached after first call -- no per-call disk I/O).
    # _resolve then applies the full three-level precedence chain:
    #   hardcoded defaults (_defaults.py)
    #   -> config file (effective_truthy/effective_falsy already resolved there)
    #   -> call-site args (truthy/extend_truthy/falsy/extend_falsy)
    config = _get_config()
    effective_truthy, effective_falsy = _resolve(
        config_truthy=config.effective_truthy,
        config_falsy=config.effective_falsy,
        truthy=truthy,
        falsy=falsy,
        extend_truthy=extend_truthy,
        extend_falsy=extend_falsy,
    )

    # Overlapping sets are a caller mistake, not a runtime error. Warn so the
    # problem is visible, then let truthy win to stay consistent and predictable.
    overlap = effective_truthy & effective_falsy
    if overlap:
        _logger.warning(
            "Overlapping truthy/falsy values (truthy wins): %s", sorted(overlap)
        )

    if normalized in effective_truthy:
        return True

    # Falsy is checked after truthy so the overlap rule above is enforced
    # without any extra branching.
    if normalized in effective_falsy:
        return False

    # Three-state logic: True/False at the call site override the config value;
    # None defers to whatever the config file says (which defaults to False if no
    # config file exists).
    effective_strict = strict if strict is not None else config.strict
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

    effective_warn = warn if warn is not None else config.warn
    if effective_warn:
        _logger.warning("Unrecognized boolean value: %r", normalized)

    # Lenient fallback: anything unrecognized is treated as falsy. This matches
    # the "off by default" mental model of environment variable feature flags.
    return False


# Private API


def _normalize_set(values: Iterable[str]) -> frozenset[str]:
    """Strip and lowercase values so they match to_bool()'s normalized input."""
    return frozenset(v.strip().lower() for v in values)


def _resolve(
    *,
    config_truthy: frozenset[str] = DEFAULT_TRUTHY,
    config_falsy: frozenset[str] = DEFAULT_FALSY,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    # Priority mirrors ruff's select/extend-select pattern:
    #   truthy        -- full replacement; caller owns the entire set
    #   extend_truthy -- additive; merges on top of config_truthy
    #   (neither)     -- use config_truthy as-is (defaults when no config file)
    # truthy takes precedence over extend_truthy; both cannot apply at once.
    if truthy is not None:
        effective_truthy = _normalize_set(truthy)
    elif extend_truthy is not None:
        effective_truthy = config_truthy | _normalize_set(extend_truthy)
    else:
        effective_truthy = config_truthy

    # Same three-level logic for the falsy side, independent of truthy.
    if falsy is not None:
        effective_falsy = _normalize_set(falsy)
    elif extend_falsy is not None:
        effective_falsy = config_falsy | _normalize_set(extend_falsy)
    else:
        effective_falsy = config_falsy

    return (effective_truthy, effective_falsy)
