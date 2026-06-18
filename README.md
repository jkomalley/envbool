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

The `envbool` command exits `0` for truthy and `1` for falsy, so it works naturally in shell scripts. Input comes from `VAR_NAME`, `--value`, or a stdin pipe (in that priority order).

```bash
envbool DEBUG && echo "debug is on"             # exit-code control flow
echo "Verbose: $(envbool --print VERBOSE)"      # print the value instead
echo "yes" | envbool && echo "truthy"           # pipe a string
envbool --strict ENABLE_CACHE || echo "bad"     # fail on unrecognized values
envbool --show-config                           # inspect effective config
```

| Flag | Description |
|---|---|
| `VAR_NAME` | Environment variable name to check. |
| `--value`, `-v TEXT` | Check a literal string instead of an env var. |
| `--strict`, `-s` | Raise an error on unrecognized values. |
| `--warn` | Log a warning on unrecognized values. |
| `--default`, `-d` | Default value if unset/empty (default: false). |
| `--print`, `-p` | Print `"true"`/`"false"` instead of using exit codes. |
| `--truthy`, `--falsy VALUE` | Replace the truthy/falsy set (repeatable). |
| `--extend-truthy`, `--extend-falsy VALUE` | Add to the truthy/falsy set (repeatable). |
| `--show-config` | Print the effective configuration and exit. |

`--strict`/`--warn` default to the config file setting when omitted. `--show-config` is mutually exclusive with `VAR_NAME`, `--value`, `--print`, and `--default`, but can be combined with the value-set flags to preview overrides.

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

envbool caches its config file for the process lifetime, so tests that use temporary config files need to clear that cache between runs. Add an autouse fixture:

```python
# conftest.py
import pytest
from envbool._config import _reset_config

@pytest.fixture(autouse=True)
def _reset_envbool_config():
    yield
    _reset_config()
```

`_reset_config()` is private but stable and intended for exactly this use.

### Exception handling

`InvalidBoolValueError` (strict mode, also a `ValueError`) and `ConfigError` (malformed config file) both inherit from `EnvBoolError`, so you can catch either specifically or the whole library at once:

```python
from envbool import envbool, InvalidBoolValueError

try:
    result = envbool("MY_VAR", strict=True)
except InvalidBoolValueError as e:
    print(e.var, e.value, e.truthy, e.falsy)  # "MY_VAR" "maybe" frozenset(...) frozenset(...)
```

`ConfigError` carries the offending file path via `e.path`.

### Logging

envbool logs to the standard `logging` module under the `"envbool"` namespace, with no handlers attached — configure it the same way you would any library logger (`logging.getLogger("envbool")`). It logs `DEBUG` for config discovery and `WARNING` for overlapping truthy/falsy values or, when `warn=True` (or the config sets `warn = true`), unrecognized values in lenient mode.

### Tri-state limitation

`envbool()` always returns `bool` — it can't distinguish an unset variable from one set to `""`; both return `default`. If you need that distinction, check `os.environ` directly before calling `envbool()`.

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)
