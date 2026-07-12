"""Built-in truthy/falsy value sets, and the shared set-resolution helpers.

These live in the same leaf module (no imports from elsewhere in envbool) so
both _core.py (call-site truthy/falsy args) and set_defaults() (added in the
same PR) can use them without a circular import.
"""

__all__ = ["DEFAULT_FALSY", "DEFAULT_TRUTHY"]

from collections.abc import Iterable

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
