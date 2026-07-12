"""Built-in truthy/falsy sets, set-resolution helpers, and process-level defaults.

The Defaults instance held here is consulted by to_bool()/envbool() whenever a
call-site strict/warn argument is None or no truthy/falsy override is given.

Public surface:
    DEFAULT_TRUTHY   -- the built-in truthy set
    DEFAULT_FALSY    -- the built-in falsy set
    Defaults         -- frozen dataclass with resolved process-level settings
    get_defaults()   -- returns the active Defaults
    set_defaults()   -- replaces the active Defaults, built from the built-ins
    reset_defaults() -- restores the built-in Defaults; for test fixtures

This is a leaf module (no imports from elsewhere in envbool) so _core.py can
import from it without a circular dependency.
"""

__all__ = [
    "DEFAULT_FALSY",
    "DEFAULT_TRUTHY",
    "Defaults",
    "get_defaults",
    "reset_defaults",
    "set_defaults",
]

import threading
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})


def _normalize_set(values: Iterable[str]) -> frozenset[str]:
    """Strip and lowercase values so they match to_bool()'s normalized input."""
    return frozenset(v.strip().lower() for v in values)


def _apply_replace_or_extend(
    base: frozenset[str],
    replace: Iterable[str] | None,
    extend: Iterable[str] | None,
) -> frozenset[str]:
    """Resolve a value set using replace/extend/fall-back-to-base precedence.

    Shared by _resolve() (call-site truthy/falsy args, in _core.py) and
    set_defaults() (below) since both layer their inputs on top of a base set
    using the same ruff select/extend-select pattern:
        replace -- full replacement; caller owns the entire set
        extend  -- additive; merges on top of base
        neither -- use base as-is
    replace takes precedence over extend; both cannot apply at once.

    Args:
        base: The starting set to fall back to or extend.
        replace: If not None, fully replaces base (normalized).
        extend: If not None and replace is None, merged on top of base.

    Returns:
        The resolved, normalized frozenset.
    """
    if replace is not None:
        return _normalize_set(replace)
    if extend is not None:
        return base | _normalize_set(extend)
    return base


@dataclass(frozen=True)
class Defaults:
    """Process-level defaults consulted when a call-site argument is None.

    Attributes:
        strict: When True, unrecognized values raise InvalidBoolValueError.
        warn: When True, unrecognized values in lenient mode emit a WARNING log.
        effective_truthy: Fully resolved truthy set (after extend/replace logic).
        effective_falsy: Fully resolved falsy set (after extend/replace logic).
    """

    strict: bool = False
    warn: bool = False
    effective_truthy: frozenset[str] = DEFAULT_TRUTHY
    effective_falsy: frozenset[str] = DEFAULT_FALSY


class _DefaultsCache:
    # Building a Defaults() is pure in-memory work (no disk I/O), so the cache
    # starts pre-populated -- readers never need a "not built yet" branch. Only
    # writers (set_defaults/reset_defaults) take the lock, so a concurrent
    # writer can't produce a torn read.

    value: Defaults = Defaults()
    lock: threading.Lock = threading.Lock()


_cache = _DefaultsCache()


def get_defaults() -> Defaults:
    """Return the active process-level defaults.

    Returns:
        The current Defaults -- built-ins, or whatever set_defaults() last set.
    """
    return _cache.value


def _validated_tuple(name: str, values: Iterable[str] | None) -> tuple[str, ...] | None:
    """Materialize an Iterable[str] argument once, validating every member.

    Iterables (e.g. generators) can only be consumed once; materializing here
    (rather than validating then re-passing the original iterable) avoids
    silently resolving to an empty set on the second pass.

    Raises:
        TypeError: If any member is not a str.
    """
    if values is None:
        return None
    materialized = tuple(values)
    for item in materialized:
        if not isinstance(item, str):
            raise TypeError(
                f"{name} must be an iterable of strings, got {type(item).__name__!r}"
            )
    return materialized


def set_defaults(
    *,
    strict: bool | None = None,
    warn: bool | None = None,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> None:
    """Set process-level defaults consulted when a call-site argument is None.

    Each call replaces the defaults starting from the hardcoded built-ins --
    it does not merge with a previous set_defaults() call. Call this once at
    application startup rather than threading strict=/truthy=/etc. through
    every envbool()/to_bool() call site.

    Args:
        strict: Raise on unrecognized values by default. None keeps the
            built-in (False).
        warn: Log a warning on unrecognized values by default. None keeps the
            built-in (False).
        truthy: Replaces the built-in truthy set.
        falsy: Replaces the built-in falsy set.
        extend_truthy: Extends the built-in truthy set.
        extend_falsy: Extends the built-in falsy set.

    Raises:
        TypeError: If strict/warn are not bool, or truthy/falsy/extend_truthy/
            extend_falsy contain a non-string member.
    """
    if strict is not None and not isinstance(strict, bool):
        raise TypeError(f"strict must be a bool, got {type(strict).__name__!r}")
    if warn is not None and not isinstance(warn, bool):
        raise TypeError(f"warn must be a bool, got {type(warn).__name__!r}")

    truthy = _validated_tuple("truthy", truthy)
    falsy = _validated_tuple("falsy", falsy)
    extend_truthy = _validated_tuple("extend_truthy", extend_truthy)
    extend_falsy = _validated_tuple("extend_falsy", extend_falsy)

    new_defaults = Defaults(
        strict=strict if strict is not None else False,
        warn=warn if warn is not None else False,
        effective_truthy=_apply_replace_or_extend(
            DEFAULT_TRUTHY, truthy, extend_truthy
        ),
        effective_falsy=_apply_replace_or_extend(DEFAULT_FALSY, falsy, extend_falsy),
    )
    with _cache.lock:
        _cache.value = new_defaults


def reset_defaults() -> None:
    """Restore built-in defaults, discarding any set_defaults() override.

    Intended for test fixtures: call in an autouse fixture teardown so a
    set_defaults() call in one test doesn't leak into the next.
    """
    with _cache.lock:
        _cache.value = Defaults()
