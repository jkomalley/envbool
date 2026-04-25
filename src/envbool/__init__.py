"""envbool -- coerce environment variables and strings into booleans.

Import everything you need directly from this package:

    from envbool import envbool, to_bool, InvalidBoolValueError

For except clauses, envbool.exceptions is also importable by name:

    from envbool.exceptions import InvalidBoolValueError

Available names:
    envbool()             -- read an env var and coerce to bool (primary API)
    to_bool()             -- coerce an arbitrary string to bool (no os.environ)
    load_config()         -- inspect or preload the process-level config cache
    EnvBoolConfig         -- frozen dataclass returned by load_config()
    DEFAULT_TRUTHY        -- built-in truthy set (frozenset)
    DEFAULT_FALSY         -- built-in falsy set (frozenset)
    EnvBoolError          -- base exception for all envbool errors
    InvalidBoolValueError -- raised in strict mode for unrecognized values
    ConfigError           -- raised for malformed or unreadable config files
"""
# All implementation lives in private underscore-prefixed modules so the public
# surface can be reshaped without breaking imports. Do not import from _core,
# _env, _config, _cli, or _defaults directly.

from envbool._config import EnvBoolConfig, load_config
from envbool._core import to_bool
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY
from envbool._env import envbool
from envbool.exceptions import ConfigError, EnvBoolError, InvalidBoolValueError

__all__ = [
    "DEFAULT_FALSY",
    "DEFAULT_TRUTHY",
    "ConfigError",
    "EnvBoolConfig",
    "EnvBoolError",
    "InvalidBoolValueError",
    "envbool",
    "load_config",
    "to_bool",
]
