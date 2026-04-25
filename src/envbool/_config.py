"""Config file discovery, loading, caching, and EnvBoolConfig dataclass.

Discovery priority (first found wins):
  1. Project-level: walk up from CWD looking for envbool.toml or [tool.envbool]
     in pyproject.toml. Walk stops at boundary markers or pyproject.toml.
  2. User-level: <platformdirs.user_config_dir("envbool")>/config.toml

The loaded config is cached for the lifetime of the process (double-checked
locking for thread safety). Call _reset_config() in test fixtures to clear it.

Public surface:
    EnvBoolConfig   -- frozen dataclass with resolved settings
    load_config()   -- returns the cached (or freshly loaded) config
    _reset_config() -- clears the cache; for test use only
"""

import logging
import os
import threading
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY
from envbool.exceptions import ConfigError

__all__ = ["EnvBoolConfig", "load_config"]

_logger = logging.getLogger(__name__)

# Boundary markers that signal "you have reached the project root -- stop walking."
# pyproject.toml is handled separately because it is both a boundary and a potential
# config source (checked for [tool.envbool] before the walk stops).
_BOUNDARY_MARKERS: frozenset[str] = frozenset({".git", ".hg", "setup.py", "setup.cfg"})

# Safety cap: never walk more than this many directory levels from CWD. Prevents
# runaway traversal in CI/CD environments or Docker containers without markers.
_MAX_WALK_DEPTH: int = 10


@dataclass(frozen=True)
class EnvBoolConfig:
    """Resolved configuration for this process, loaded from a config file or defaults.

    Attributes:
        strict: When True, unrecognized values raise InvalidBoolValueError.
        warn: When True, unrecognized values in lenient mode emit a WARNING log.
        effective_truthy: Fully resolved truthy set (after extend/replace logic).
        effective_falsy: Fully resolved falsy set (after extend/replace logic).
        source_path: Which file was loaded, or None if using hardcoded defaults.
    """

    strict: bool = False
    warn: bool = False
    # field() is required here because frozenset is not a primitive type -- Python's
    # dataclass machinery rejects non-primitive mutable-looking defaults without it,
    # even though frozenset is immutable.
    effective_truthy: frozenset[str] = field(default_factory=lambda: DEFAULT_TRUTHY)
    effective_falsy: frozenset[str] = field(default_factory=lambda: DEFAULT_FALSY)
    source_path: Path | None = None


class _ConfigCache:
    """Mutable wrapper for the process-level config singleton.

    A class attribute instead of a bare module-level variable avoids the need
    for 'global' statements when updating the cached value. The lock lives here
    too so all cache state travels together.
    """

    config: EnvBoolConfig | None = None
    lock: threading.Lock = threading.Lock()


_cache = _ConfigCache()


def load_config() -> EnvBoolConfig:
    """Return the active config, loading from disk on first call.

    Subsequent calls return the cached instance with no disk I/O. Use this to
    inspect or preload the config at application startup.

    Returns:
        The resolved EnvBoolConfig for this process.

    Raises:
        ConfigError: If a config file is found but malformed or has invalid values.
    """
    return _get_config()


def _get_config() -> EnvBoolConfig:
    """Internal cached accessor with double-checked locking.

    The outer check avoids lock contention on the hot path (all calls after first
    load). The inner check prevents duplicate disk I/O if two threads race on the
    very first call.
    """
    if _cache.config is not None:
        return _cache.config
    with _cache.lock:
        if _cache.config is not None:  # another thread may have loaded while we waited
            return _cache.config
        _cache.config = _load_config_from_disk()
        return _cache.config


def _reset_config() -> None:
    """Clear the cached config so the next call reloads from disk.

    For test use only -- not part of the public API. Intended to be called in a
    pytest autouse fixture so each test starts with a clean slate:

        @pytest.fixture(autouse=True)
        def _reset_envbool_config():
            yield
            envbool._reset_config()
    """
    with _cache.lock:
        _cache.config = None


def _load_config_from_disk() -> EnvBoolConfig:
    """Discover and parse the config file, returning EnvBoolConfig.

    Uses a raw os.environ.get() -- not envbool() itself -- to check
    ENVBOOL_NO_CONFIG. Calling envbool() here would trigger _get_config() again
    before _config is set, causing infinite recursion.
    """
    if os.environ.get("ENVBOOL_NO_CONFIG") == "1":
        _logger.debug("ENVBOOL_NO_CONFIG=1 -- skipping config file discovery")
        return EnvBoolConfig()

    # Project-level: walk up from CWD
    project_config = _find_project_config()
    if project_config is not None:
        return project_config

    # User-level: platformdirs fallback
    user_config = _find_user_config()
    if user_config is not None:
        return user_config

    _logger.debug("No config file found -- using hardcoded defaults")
    return EnvBoolConfig()


def _find_project_config() -> EnvBoolConfig | None:
    """Walk up the directory tree from CWD looking for a project-level config.

    Returns the parsed EnvBoolConfig if a config is found, None otherwise.
    Stops early at boundary markers or after _MAX_WALK_DEPTH levels.
    """
    current = Path.cwd()
    for _ in range(_MAX_WALK_DEPTH):
        # envbool.toml takes priority over pyproject.toml in the same directory.
        envbool_toml = current / "envbool.toml"
        if envbool_toml.is_file():
            _logger.debug("Found config: %s", envbool_toml)
            return _parse_toml_file(envbool_toml)

        pyproject = current / "pyproject.toml"
        if pyproject.is_file():
            # pyproject.toml is both a potential config source AND a boundary marker.
            # We check for [tool.envbool] first; if present, use it. Either way, stop
            # walking -- a pyproject.toml signals "you've reached the project root."
            config = _try_pyproject(pyproject)
            if config is not None:
                _logger.debug("Found config in [tool.envbool]: %s", pyproject)
            else:
                _logger.debug(
                    "pyproject.toml has no [tool.envbool] -- stopping walk at %s",
                    current,
                )
            return config  # may be None -- caller treats None as "not found"

        # Standard boundary markers (not config sources, just stop signals).
        if any((current / marker).exists() for marker in _BOUNDARY_MARKERS):
            _logger.debug("Boundary marker found at %s -- stopping walk", current)
            return None

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent

    _logger.debug("Depth cap (%d) reached -- stopping walk", _MAX_WALK_DEPTH)
    return None


def _find_user_config() -> EnvBoolConfig | None:
    """Check the platformdirs user config directory for config.toml.

    Returns the parsed EnvBoolConfig if found, None if the file does not exist.
    If platformdirs cannot determine the config dir (very rare), returns None
    rather than crashing.
    """
    try:
        config_dir = Path(platformdirs.user_config_dir("envbool"))
    except Exception:  # noqa: BLE001 -- platformdirs failure is non-fatal
        _logger.debug("platformdirs could not determine user config dir -- skipping")
        return None

    config_file = config_dir / "config.toml"
    if not config_file.is_file():
        return None

    _logger.debug("Found user config: %s", config_file)
    return _parse_toml_file(config_file)


def _try_pyproject(path: Path) -> EnvBoolConfig | None:
    """Parse path as a pyproject.toml and return config from [tool.envbool].

    Returns None (not an error) if the section is absent -- the caller
    interprets that as "stop walking but no config found."

    Raises:
        ConfigError: If the TOML is malformed or [tool.envbool] has invalid values.
    """
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        err = ConfigError(f"Malformed TOML in {path}: {exc}")
        err.path = path
        raise err from exc

    section = data.get("tool", {}).get("envbool")
    if section is None:
        return None
    if not isinstance(section, dict):
        err = ConfigError(f"[tool.envbool] must be a table in {path}")
        err.path = path
        raise err
    return _parse_config(section, path)


def _parse_toml_file(path: Path) -> EnvBoolConfig:
    """Read and parse a standalone TOML config file (envbool.toml or user config.toml).

    Args:
        path: Path to the TOML file.

    Returns:
        Parsed and validated EnvBoolConfig.

    Raises:
        ConfigError: If the file is malformed TOML or contains invalid values.
    """
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        err = ConfigError(f"Malformed TOML in {path}: {exc}")
        err.path = path
        raise err from exc

    return _parse_config(data, path)


def _parse_config(data: dict, path: Path) -> EnvBoolConfig:
    """Validate a raw TOML dict and resolve it into an EnvBoolConfig.

    Unknown keys are silently ignored so config files stay forward-compatible as
    new options are added. Known keys are type-checked strictly -- wrong types
    (e.g. strict = "yes" instead of strict = true) raise ConfigError with a message
    that names the expected type, since a type mismatch is almost certainly a typo.

    The extend/replace logic here mirrors _resolve() in core.py:
      - "truthy" replaces DEFAULT_TRUTHY entirely
      - "extend_truthy" adds to DEFAULT_TRUTHY
      - "truthy" takes priority when both present (ruff's select/extend-select pattern)

    Args:
        data: Parsed TOML key/value pairs (the [tool.envbool] section or top-level).
        path: Source file path, attached to any ConfigError for diagnostics.

    Returns:
        Resolved EnvBoolConfig with effective_truthy/effective_falsy fully computed.

    Raises:
        ConfigError: For type mismatches or malformed list elements.
    """
    # --- bool fields ---
    strict = _get_bool_field(data, "strict", path)
    warn = _get_bool_field(data, "warn", path)

    # --- set fields: apply extend/replace logic ---
    # truthy replaces DEFAULT_TRUTHY; extend_truthy adds to it; truthy wins if both.
    raw_truthy = _get_str_list_field(data, "truthy", path)
    raw_extend_truthy = _get_str_list_field(data, "extend_truthy", path)
    if raw_truthy is not None:
        effective_truthy = _normalize_set(raw_truthy)
    elif raw_extend_truthy is not None:
        effective_truthy = DEFAULT_TRUTHY | _normalize_set(raw_extend_truthy)
    else:
        effective_truthy = DEFAULT_TRUTHY

    # Same extend/replace logic for the falsy side, independent of truthy.
    raw_falsy = _get_str_list_field(data, "falsy", path)
    raw_extend_falsy = _get_str_list_field(data, "extend_falsy", path)
    if raw_falsy is not None:
        effective_falsy = _normalize_set(raw_falsy)
    elif raw_extend_falsy is not None:
        effective_falsy = DEFAULT_FALSY | _normalize_set(raw_extend_falsy)
    else:
        effective_falsy = DEFAULT_FALSY

    _logger.debug(
        "Config loaded from %s: strict=%s warn=%s truthy=%s falsy=%s",
        path,
        strict,
        warn,
        sorted(effective_truthy),
        sorted(effective_falsy),
    )

    return EnvBoolConfig(
        strict=strict if strict is not None else False,
        warn=warn if warn is not None else False,
        effective_truthy=effective_truthy,
        effective_falsy=effective_falsy,
        source_path=path,
    )


def _normalize_set(values: list[str]) -> frozenset[str]:
    """Strip and lowercase values so they match to_bool()'s normalized input."""
    return frozenset(v.strip().lower() for v in values)


def _get_bool_field(data: dict, key: str, path: Path) -> bool | None:
    """Extract a bool field from data, returning None if absent.

    Raises:
        ConfigError: If the key is present but not a Python bool (TOML boolean).
    """
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, bool):
        err = ConfigError(
            f"Config error in {path}: '{key}' must be a boolean (true or false),"
            f" got {type(value).__name__!r}"
        )
        err.path = path
        raise err
    return value


def _get_str_list_field(data: dict, key: str, path: Path) -> list[str] | None:
    """Extract a list-of-strings field from data, returning None if absent.

    Raises:
        ConfigError: If the key is present but not a list, or contains non-strings.
    """
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, list):
        err = ConfigError(
            f"Config error in {path}: '{key}' must be an array of strings,"
            f" got {type(value).__name__!r}"
        )
        err.path = path
        raise err
    for i, item in enumerate(value):
        if not isinstance(item, str):
            err = ConfigError(
                f"Config error in {path}: '{key}[{i}]' must be a string,"
                f" got {type(item).__name__!r}"
            )
            err.path = path
            raise err
    return value
