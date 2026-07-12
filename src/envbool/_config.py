"""In-memory process-level config cache.

Config file discovery (envbool.toml, [tool.envbool] in pyproject.toml, and
the user-level config.toml fallback) was removed in 0.4.0 in favor of the
explicit envbool.set_defaults() API -- see CHANGELOG.md. This module now just
holds a single EnvBoolConfig built from hardcoded defaults.

Public surface:
    EnvBoolConfig   -- frozen dataclass with resolved settings
    load_config()   -- returns the active config
    _reset_config() -- restores the default config; for test use only
"""

import threading
from dataclasses import dataclass

from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY

__all__ = ["EnvBoolConfig", "load_config"]


@dataclass(frozen=True)
class EnvBoolConfig:
    """Resolved configuration for this process.

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


class _ConfigCache:
    # Building an EnvBoolConfig is pure in-memory work (no disk I/O since
    # config-file discovery was removed), so the cache starts pre-populated --
    # readers never need a "not built yet" branch. The lock protects writers
    # (_reset_config) so tests can't produce a torn read.

    config: EnvBoolConfig = EnvBoolConfig()
    lock: threading.Lock = threading.Lock()


_cache = _ConfigCache()


def load_config() -> EnvBoolConfig:
    """Return the active config.

    Returns:
        The resolved EnvBoolConfig for this process.
    """
    return _get_config()


def _get_config() -> EnvBoolConfig:
    # Kept under this name because _core.py imports it; load_config() is the
    # public alias.
    return _cache.config


def _reset_config() -> None:
    """Restore the default config.

    For test use only -- not part of the public API. Called in the autouse
    conftest fixture so each test starts with a clean slate.
    """
    with _cache.lock:
        _cache.config = EnvBoolConfig()
