# envbool

Coerce environment variables to booleans.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![MIT License](https://img.shields.io/badge/license-MIT-green)

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

```bash
# Control flow via exit code
envbool DEBUG && echo "debug is on"

# Print the resolved value
echo "Verbose: $(envbool --print VERBOSE)"

# Pipe a string
echo "yes" | envbool && echo "truthy"

# Strict mode
envbool --strict ENABLE_CACHE || echo "cache is off or misconfigured"
```

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
| `load_config()` | Inspect the loaded config |
| `DEFAULT_TRUTHY` | `frozenset` of built-in truthy strings |
| `DEFAULT_FALSY` | `frozenset` of built-in falsy strings |
| `InvalidBoolValueError` | Raised in strict mode on unrecognized values |
| `ConfigError` | Raised when a config file is malformed |

Both `envbool()` and `to_bool()` accept the same keyword arguments: `default`, `strict`, `warn`, `truthy`, `falsy`, `extend_truthy`, `extend_falsy`. `truthy`/`falsy` replace the effective set; `extend_truthy`/`extend_falsy` add to it.
