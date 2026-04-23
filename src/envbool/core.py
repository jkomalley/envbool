"""Core coercion logic: to_bool, set resolution, default sets."""

from collections.abc import Iterable

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})

# Public API

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
