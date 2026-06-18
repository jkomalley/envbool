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

```bash
# Control flow via exit code
envbool DEBUG && echo "debug is on"

# Print the resolved value instead of using the exit code
echo "Verbose: $(envbool --print VERBOSE)"

# Coerce a literal string instead of reading an env var
envbool --value "yes" && echo "truthy"

# Pipe a string
echo "yes" | envbool && echo "truthy"

# Strict mode: fail loudly on unrecognized values
envbool --strict ENABLE_CACHE || echo "cache is off or misconfigured"

# Warn (but don't fail) on unrecognized values, e.g. while migrating to strict
envbool --warn LEGACY_FLAG

# Inspect the effective configuration (file path, strict, warn, value sets)
envbool --show-config
```

### Flag reference

| Flag | Description |
|---|---|
| `VAR_NAME` | Environment variable name to check. |
| `--value`, `-v TEXT` | Check a literal string instead of an env var. |
| `--strict`, `-s` | Raise an error on unrecognized values. |
| `--warn` | Log a warning on unrecognized values. |
| `--default`, `-d` | Default value if unset/empty (default: false). |
| `--print`, `-p` | Print `"true"`/`"false"` instead of using exit codes. |
| `--truthy VALUE` | Replace the truthy set with `VALUE` (repeatable). |
| `--falsy VALUE` | Replace the falsy set with `VALUE` (repeatable). |
| `--extend-truthy VALUE` | Add `VALUE` to the truthy set (repeatable). |
| `--extend-falsy VALUE` | Add `VALUE` to the falsy set (repeatable). |
| `--show-config` | Print the effective configuration and exit. |

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:

- Resetting the config cache between tests (`_reset_config()`)
- `InvalidBoolValueError` and `ConfigError` attributes for fine-grained exception handling
- Configuring envbool's logging output
- The tri-state (unset vs. empty string) limitation and how to work around it

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)
