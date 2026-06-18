<div align="center">

# envbool

**Coerce environment variables and strings into booleans — sensibly.**

[![PyPI version](https://img.shields.io/pypi/v/envbool)](https://pypi.org/project/envbool/)
[![Python versions](https://img.shields.io/pypi/pyversions/envbool)](https://pypi.org/project/envbool/)
[![License: MIT](https://img.shields.io/github/license/jkomalley/envbool)](LICENSE)
[![CI](https://github.com/jkomalley/envbool/actions/workflows/ci.yml/badge.svg)](https://github.com/jkomalley/envbool/actions/workflows/ci.yml)

</div>

---

Reading a boolean out of the environment is the kind of thing every project
reinvents, slightly differently, in slightly buggy ways:

```python
DEBUG   = os.environ.get("DEBUG",   "").lower() in ("1", "true", "yes")
VERBOSE = os.environ.get("VERBOSE", "").lower() in ("1", "true", "yes")
CACHE   = os.environ.get("CACHE",   "").lower() in ("1", "true", "yes")
```

`envbool` is that snippet, done once and done properly:

```python
from envbool import envbool

DEBUG   = envbool("DEBUG")
VERBOSE = envbool("VERBOSE")
CACHE   = envbool("CACHE")
```

## Features

- **Lenient by default, strict when you want it.** Unrecognized values quietly
  become `False`, or raise on demand to catch typos in production config.
- **Always returns `bool`.** No `None`, no surprises in your type signatures.
- **Customizable value sets.** Replace or extend the truthy/falsy words your
  environment uses.
- **Config files.** Share defaults across a project via `envbool.toml` or
  `[tool.envbool]` in `pyproject.toml`.
- **A CLI for shell scripts.** Exit codes map to truthiness, so it drops
  straight into `&&` / `||` chains.
- **Zero ceremony.** One dependency, fully typed, Python 3.11+.

## Contents

- [Installation](#installation)
- [Usage](#usage)
- [Command-line interface](#command-line-interface)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Advanced topics](#advanced-topics)
- [Contributing](#contributing)
- [License](#license)

## Installation

```bash
pip install envbool
# or
uv add envbool
```

## Usage

### The basics

`envbool` is **lenient by default**: anything not recognized as truthy returns
`False`, and unset or empty variables return the default.

```python
from envbool import envbool

DEBUG = envbool("DEBUG")                 # False if unset or empty
CACHE = envbool("CACHE", default=True)   # True if unset or empty
```

The built-in truthy values are `true`, `1`, `yes`, `on`; the falsy values are
`false`, `0`, `no`, `off`. Comparison is case-insensitive and ignores
surrounding whitespace.

### Strict mode

Pass `strict=True` to raise `InvalidBoolValueError` on anything outside the
truthy/falsy sets — ideal for failing fast on a misconfigured deployment.

```python
import sys
from envbool import envbool, InvalidBoolValueError

try:
    USE_SSL = envbool("USE_SSL", strict=True)
except InvalidBoolValueError as e:
    sys.exit(f"Bad value for USE_SSL: {e.value!r}")
```

### Custom value sets

When your environment speaks a different dialect, **extend** the defaults or
**replace** them outright:

```python
# Add to the built-in sets
FEATURE = envbool("FEATURE_FLAG", extend_truthy={"enabled", "y"})

# Replace them entirely
LOCALE = envbool("USE_METRIC", truthy={"metric"}, falsy={"imperial"})
```

### Coercing arbitrary strings

Use `to_bool` for values that don't come from the environment. It accepts the
same keyword arguments as `envbool`.

```python
from envbool import to_bool

to_bool("yes")                 # True
to_bool("0")                   # False
to_bool("maybe", strict=True)  # raises InvalidBoolValueError
```

## Command-line interface

The `envbool` command exits `0` for truthy, `1` for falsy, and `2` on error, so
it composes naturally with shell control flow.

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

Input is taken from a `VAR_NAME` argument, the `--value` flag, or a stdin pipe —
in that order of priority.

```console
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

A few rules worth knowing:

- Omitting `--strict` / `--warn` defers to the config file setting.
- `VAR_NAME` and `--value` are mutually exclusive.
- `--show-config` prints the effective configuration and exits. It cannot be
  combined with `VAR_NAME`, `--value`, `--print`, or `--default`, but it *can*
  take the value-set flags to preview overrides.
- With no `VAR_NAME`, `--value`, or piped stdin, the CLI prints usage and exits `2`.

## Configuration

Share defaults across a project by dropping an `envbool.toml` at its root (or a
`[tool.envbool]` table in `pyproject.toml`):

```toml
# envbool.toml
strict = true
extend_truthy = ["enabled"]
extend_falsy  = ["disabled"]
```

`envbool` walks up from the current directory to find the nearest project config,
then falls back to a user-level `config.toml` in the platform's standard config
directory (`~/.config/envbool/` on Linux, `~/Library/Application Support/envbool/`
on macOS), resolved via [platformdirs](https://pypi.org/project/platformdirs/).

Values resolve in three layers, each overriding the last:

```
built-in defaults  →  config file  →  function arguments / CLI flags
```

Set `ENVBOOL_NO_CONFIG=1` to skip config discovery entirely.

## API reference

| Symbol | Description |
| --- | --- |
| `envbool(var, **opts)` | Read an environment variable and return `bool`. |
| `to_bool(value, **opts)` | Coerce a string to `bool`. |
| `load_config()` | Load and return the active `EnvBoolConfig` (cached). |
| `EnvBoolConfig` | Frozen dataclass: `strict`, `warn`, `effective_truthy`, `effective_falsy`, `source_path`. |
| `DEFAULT_TRUTHY` | `frozenset` of the built-in truthy strings. |
| `DEFAULT_FALSY` | `frozenset` of the built-in falsy strings. |
| `EnvBoolError` | Base class for every exception the library raises. |
| `InvalidBoolValueError` | Raised in strict mode for unrecognized values. Also a `ValueError`. |
| `ConfigError` | Raised when a config file is malformed. |

`envbool()` and `to_bool()` share the same keyword-only options:

| Option | Type | Default | Meaning |
| --- | --- | --- | --- |
| `default` | `bool` | `False` | Returned for unset/empty input. |
| `strict` | `bool \| None` | `None` | Raise on unrecognized values (`None` defers to config). |
| `warn` | `bool \| None` | `None` | Log a warning on unrecognized values (`None` defers to config). |
| `truthy` / `falsy` | `Iterable[str] \| None` | `None` | **Replace** the effective set. |
| `extend_truthy` / `extend_falsy` | `Iterable[str] \| None` | `None` | **Extend** the effective set. |

## Advanced topics

### Exception handling

Every exception inherits from `EnvBoolError`, so a single `except EnvBoolError`
catches the whole library. Catch a specific subclass when you need its detail:

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

`InvalidBoolValueError` also subclasses the built-in `ValueError`, so existing
`except ValueError` handlers keep working. Its message spells out exactly what
was expected:

```
InvalidBoolValueError: Invalid boolean value for MY_VAR: 'maybe'
  Expected truthy: 1, on, true, yes
  Expected falsy:  0, false, no, off
```

`ConfigError` is raised when a config file is found but malformed (for example,
`strict = "yes"` instead of `strict = true`). It carries the offending path on
`e.path`.

### Logging

`envbool` logs through the standard `logging` module under the `"envbool"`
namespace and attaches no handlers of its own — configure it like any other
library logger:

```python
import logging

logging.getLogger("envbool").setLevel(logging.DEBUG)
logging.getLogger("envbool").addHandler(logging.StreamHandler())
```

| Level | When |
| --- | --- |
| `DEBUG` | A config file was discovered and loaded, or none was found. |
| `WARNING` | An unrecognized value fell through in lenient mode (only when `warn=True`). |
| `WARNING` | The truthy and falsy sets overlap (truthy wins). |

### The unset-vs-empty distinction

`envbool()` always returns `bool` and deliberately cannot tell an unset variable
apart from one set to the empty string — both yield `default`. Most deployment
tooling can't distinguish the two either, and a plain `bool` keeps call sites
clean. When you genuinely need the distinction, check `os.environ` yourself:

```python
import os
from envbool import envbool

if "MY_VAR" not in os.environ:
    ...  # truly unset — handle the "not configured" case
else:
    result = envbool("MY_VAR")
```

### Testing code that uses envbool

`envbool` loads its config file once and caches it for the process lifetime. If
your tests create temporary config files, clear that cache between them with an
autouse fixture:

```python
# conftest.py
import pytest
from envbool._config import _reset_config

@pytest.fixture(autouse=True)
def _reset_envbool_config():
    yield
    _reset_config()
```

`_reset_config()` is private but stable and exists for exactly this purpose; it
clears the cache under a lock, so it is safe to call from any thread.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup, project layout, and the conventions this repo follows.

## License

Released under the [MIT License](LICENSE).
