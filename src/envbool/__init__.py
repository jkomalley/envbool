"""envbool -- coerce environment variables and strings into booleans.

Import everything you need directly from this package:

    from envbool import envbool, to_bool, InvalidBoolValueError

For except clauses, envbool.exceptions is also importable by name:

    from envbool.exceptions import InvalidBoolValueError

Available names:
    envbool()             -- read an env var and coerce to bool (primary API)
    to_bool()             -- coerce an arbitrary string to bool (no os.environ)
    set_defaults()        -- set process-level strict/warn/truthy/falsy defaults
    get_defaults()        -- inspect the active process-level Defaults
    reset_defaults()      -- restore built-in defaults (for test fixtures)
    Defaults              -- frozen dataclass returned by get_defaults()
    DEFAULT_TRUTHY        -- built-in truthy set (frozenset)
    DEFAULT_FALSY         -- built-in falsy set (frozenset)
    EnvBoolError          -- base exception for all envbool errors
    InvalidBoolValueError -- raised in strict mode for unrecognized values
    MissingEnvVarError    -- raised by envbool(required=True) when a var is unset
"""
# All implementation lives in private underscore-prefixed modules so the public
# surface can be reshaped without breaking imports. Do not import from _core,
# _env, _config, _cli, or _defaults directly.

from envbool._core import to_bool
from envbool._defaults import (
    DEFAULT_FALSY,
    DEFAULT_TRUTHY,
    Defaults,
    get_defaults,
    reset_defaults,
    set_defaults,
)
from envbool._env import envbool
from envbool.exceptions import (
    EnvBoolError,
    InvalidBoolValueError,
    MissingEnvVarError,
)

__all__ = [
    "DEFAULT_FALSY",
    "DEFAULT_TRUTHY",
    "Defaults",
    "EnvBoolError",
    "InvalidBoolValueError",
    "MissingEnvVarError",
    "envbool",
    "get_defaults",
    "reset_defaults",
    "set_defaults",
    "to_bool",
]
