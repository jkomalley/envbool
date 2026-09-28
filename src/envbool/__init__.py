"""envbool -- coerce environment variables and strings into booleans.

Import everything you need directly from this package:

    from envbool import envbool, to_bool, InvalidBoolValueError

For except clauses, envbool.exceptions is also importable by name:

    from envbool.exceptions import InvalidBoolValueError

Available names:
    envbool()              -- read an env var and coerce to bool (primary API)
    to_bool()              -- coerce an arbitrary string to bool (no os.environ)
    DEFAULT_TRUTHY         -- built-in truthy set (frozenset)
    DEFAULT_FALSY          -- built-in falsy set (frozenset)
    EnvBoolError           -- base exception for all envbool errors
    InvalidBoolValueError  -- raised in strict mode for unrecognized values
    ConflictingValuesError -- raised in strict mode when truthy/falsy overlap
    MissingEnvVarError     -- raised by envbool(required=True) when a var is unset
"""
# All implementation lives in private underscore-prefixed modules so the public
# surface can be reshaped without breaking imports. Do not import from _core,
# _env, or _cli directly.

from envbool._core import DEFAULT_FALSY, DEFAULT_TRUTHY, to_bool
from envbool._env import envbool
from envbool.exceptions import (
    ConflictingValuesError,
    EnvBoolError,
    InvalidBoolValueError,
    MissingEnvVarError,
)

__all__ = [
    "DEFAULT_FALSY",
    "DEFAULT_TRUTHY",
    "ConflictingValuesError",
    "EnvBoolError",
    "InvalidBoolValueError",
    "MissingEnvVarError",
    "envbool",
    "to_bool",
]
