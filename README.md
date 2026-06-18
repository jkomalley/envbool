# envbool

Coerce environment variables to booleans.

[![PyPI version](https://img.shields.io/pypi/v/envbool)](https://pypi.org/project/envbool/)
[![Python versions](https://img.shields.io/pypi/pyversions/envbool)](https://pypi.org/project/envbool/)
[![License: MIT](https://img.shields.io/github/license/jkomalley/envbool)](https://github.com/jkomalley/envbool/blob/main/LICENSE)
[![CI](https://github.com/jkomalley/envbool/actions/workflows/ci.yml/badge.svg)](https://github.com/jkomalley/envbool/actions/workflows/ci.yml)

---

Every project ends up with some version of this:

```python
DEBUG   = os.environ.get("DEBUG",   "").lower() in ("1", "true", "yes")
VERBOSE = os.environ.get("VERBOSE", "").lower() in ("1", "true", "yes")
CACHE   = os.environ.get("CACHE",   "").lower() in ("1", "true", "yes")
```

`envbool` replaces that:

```python
from envbool import envbool

DEBUG   = envbool("DEBUG")
VERBOSE = envbool("VERBOSE")
CACHE   = envbool("CACHE")
```

It also handles strict mode, warnings, custom value sets, config files, and a CLI for shell scripts.

---

## Installation

```bash
pip install envbool
# or
uv add envbool
```

## Usage

**Lenient by default.** Anything not recognized as truthy returns `False`. Unset and empty variables return the default.

```python
from envbool import envbool

DEBUG = envbool("DEBUG")                    # False if unset or empty
CACHE = envbool("CACHE", default=True)      # True if unset or empty
```

The built-in truthy values are `true`, `1`, `yes`, `on`. Comparison is case-insensitive.

**Strict mode** raises `InvalidBoolValueError` for unrecognized values — useful for catching typos in production config.

```python
from envbool import envbool, InvalidBoolValueError

try:
    USE_SSL = envbool("USE_SSL", strict=True)
except InvalidBoolValueError as e:
    print(f"Bad value for USE_SSL: {e.value!r}")
    sys.exit(1)
```

**Extend the value sets** when your environment uses non-standard strings.

```python
FEATURE = envbool("FEATURE_FLAG", extend_truthy={"enabled", "y"})
```

**Coerce an arbitrary string** (not from `os.environ`) with `to_bool`:

```python
from envbool import to_bool

to_bool("yes")                  # True
to_bool("0")                    # False
to_bool("maybe", strict=True)   # raises InvalidBoolValueError
```

## CLI

The `envbool` command exits `0` for truthy and `1` for falsy, so it works naturally in shell scripts.

```console
$ export DEBUG=true
$ envbool DEBUG && echo "debug is on"
debug is on

$ echo "Verbose: $(envbool --print VERBOSE)"
Verbose: false

$ echo "yes" | envbool && echo "truthy"
truthy

$ envbool --strict ENABLE_CACHE || echo "cache is off or misconfigured"
cache is off or misconfigured
```

```
$ envbool --help
usage: envbool [-h] [--value TEXT] [--strict] [--warn] [--default] [--print]
               [--truthy VALUE] [--falsy VALUE] [--extend-truthy VALUE]
               [--extend-falsy VALUE] [--show-config]
               [VAR_NAME]

Coerce an environment variable or string to a boolean.

positional arguments:
  VAR_NAME              Environment variable name to check.

options:
  -h, --help            show this help message and exit
  --value, -v TEXT      Check a literal string instead of an env var.
  --strict, -s          Raise error on unrecognized values.
  --warn                Log a warning on unrecognized values.
  --default, -d         Default value if unset/empty (default: false).
  --print, -p           Print "true" or "false" instead of using exit codes.
  --truthy VALUE        Replace the truthy set with VALUE (repeatable).
  --falsy VALUE         Replace the falsy set with VALUE (repeatable).
  --extend-truthy VALUE
                        Add VALUE to the truthy set (repeatable).
  --extend-falsy VALUE  Add VALUE to the falsy set (repeatable).
  --show-config         Print the effective configuration and exit.
```

Omitting `--strict` or `--warn` defers to the config file setting. `VAR_NAME` and `--value` are mutually exclusive. `--show-config` is mutually exclusive with `VAR_NAME`, `--value`, `--print`, and `--default`, but can be combined with the value-set flags to preview overrides.

If no `VAR_NAME`, `--value`, or stdin pipe is given, the CLI prints usage and exits `2`.

## Configuration

Put shared defaults in `envbool.toml` (or `[tool.envbool]` in `pyproject.toml`) at your project root:

```toml
strict = true
extend_truthy = ["enabled"]
extend_falsy  = ["disabled"]
```

`envbool` walks up from the current directory to find the nearest config file, then falls back to a user-level config (`~/.config/envbool/config.toml` on Linux/macOS). Function arguments always override the config.

Set `ENVBOOL_NO_CONFIG=1` to skip config discovery entirely.

## API

| Symbol | Description |
|---|---|
| `envbool(var, ...)` | Read an env var and return `bool` |
| `to_bool(value, ...)` | Coerce a string to `bool` |
| `load_config()` | Inspect the loaded config, returns an `EnvBoolConfig` |
| `EnvBoolConfig` | Frozen dataclass: `strict`, `warn`, `effective_truthy`, `effective_falsy`, `source_path` |
| `DEFAULT_TRUTHY` | `frozenset` of built-in truthy strings |
| `DEFAULT_FALSY` | `frozenset` of built-in falsy strings |
| `EnvBoolError` | Base exception for all envbool errors |
| `InvalidBoolValueError` | Raised in strict mode on unrecognized values (also an `EnvBoolError` and `ValueError`) |
| `ConfigError` | Raised when a config file is malformed (also an `EnvBoolError`) |

Both `envbool()` and `to_bool()` accept the same keyword arguments: `default`, `strict`, `warn`, `truthy`, `falsy`, `extend_truthy`, `extend_falsy`. `truthy`/`falsy` replace the effective set; `extend_truthy`/`extend_falsy` add to it.

## Advanced usage

### Testing code that calls envbool

envbool loads its config file once and caches it for the lifetime of the process. If your test suite creates temporary config files or relies on specific config state, you need to clear that cache between tests — otherwise the first test to trigger config loading will pollute all subsequent tests.

Add this fixture to your `conftest.py`:

```python
# conftest.py
import pytest
from envbool._config import _reset_config

@pytest.fixture(autouse=True)
def _reset_envbool_config():
    yield
    _reset_config()
```

`_reset_config()` is intentionally private (underscore-prefixed, not in `__all__`), but it is stable and intended for exactly this use. It clears the cache under a lock, so it is safe to call from any thread.

### Exception handling

Both exceptions below inherit from `EnvBoolError`, so `except EnvBoolError` catches either. Catch the specific one when you need its details:

```python
from envbool import envbool, InvalidBoolValueError

try:
    result = envbool("MY_VAR", strict=True)
except InvalidBoolValueError as e:
    print(e.var)    # "MY_VAR" — env var name, or None when raised from to_bool()
    print(e.value)  # "maybe" — the normalized (stripped, lowercased) value
    print(e.truthy) # frozenset({"true", "1", "yes", "on"}) — effective truthy set
    print(e.falsy)  # frozenset({"false", "0", "no", "off"}) — effective falsy set
```

`InvalidBoolValueError` is raised in strict mode for unrecognized values and also inherits from `ValueError`, so existing `except ValueError` handlers keep working. Its message includes the full expected sets:

```
InvalidBoolValueError: Invalid boolean value for MY_VAR: 'maybe'
  Expected truthy: 1, on, true, yes
  Expected falsy:  0, false, no, off
```

`ConfigError` is raised when a config file is found but malformed (e.g. `strict = "yes"` instead of `strict = true`). It carries the file path via `e.path`.

### Logging

envbool logs through the standard `logging` module under the `"envbool"` namespace. No handlers are attached by default — configure it like any other library logger:

```python
import logging
logging.getLogger("envbool").setLevel(logging.DEBUG)
logging.getLogger("envbool").addHandler(logging.StreamHandler())
```

(Or just call `logging.basicConfig(level=logging.DEBUG)` to see output from everything, envbool included.)

What gets logged:

| Level | When |
|---|---|
| `DEBUG` | Config file discovered and loaded (includes path) |
| `DEBUG` | No config file found — using hardcoded defaults |
| `WARNING` | Unrecognized value in lenient mode (only when `warn=True`) |
| `WARNING` | Overlapping truthy/falsy values (truthy wins) |

The `warn` parameter controls whether unrecognized lenient-mode values emit a warning. `None` (the default) defers to the config file setting; `True` or `False` override it:

```python
# Emit a warning when "maybe" falls through to False
envbool("MY_VAR", warn=True)

# Suppress warnings even if the config file sets warn = true
envbool("MY_VAR", warn=False)
```

### Tri-state limitation

`envbool()` always returns `bool`. It cannot distinguish between a variable that is unset and one that is set to an empty string — both return `default` (which is `False` unless you pass `default=True`).

This is a deliberate trade-off. Most deployment tooling cannot meaningfully distinguish the two states, and a `bool` return type keeps the API simple and type signatures clean.

If you need tri-state detection, check `os.environ` directly before calling `envbool()`:

```python
import os
from envbool import envbool

if "MY_VAR" not in os.environ:
    # Variable is absent — handle the "not configured" case
    ...
else:
    result = envbool("MY_VAR")
```

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)
