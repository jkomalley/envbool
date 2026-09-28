<div align="center">

# envbool

**Coerce environment variables and strings into booleans — sensibly.**

[![PyPI version](https://img.shields.io/pypi/v/envbool)](https://pypi.org/project/envbool/)
[![Snap Store](https://snapcraft.io/envbool/badge.svg)](https://snapcraft.io/envbool)
[![Python versions](https://img.shields.io/pypi/pyversions/envbool)](https://pypi.org/project/envbool/)
[![License: MIT](https://img.shields.io/github/license/jkomalley/envbool)](LICENSE)
[![CI](https://github.com/jkomalley/envbool/actions/workflows/ci.yml/badge.svg)](https://github.com/jkomalley/envbool/actions/workflows/ci.yml)

</div>

---

Reading a boolean out of the environment is the kind of thing every project
reinvents, slightly differently, in slightly buggy ways:

```python
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
VERBOSE = os.environ.get("VERBOSE", "").lower() in ("1", "true", "yes")
CACHE = os.environ.get("CACHE", "").lower() in ("1", "true", "yes")
```

`envbool` is that snippet, done once and done properly:

```python
from envbool import envbool

DEBUG = envbool("DEBUG")
VERBOSE = envbool("VERBOSE")
CACHE = envbool("CACHE")
```

## Features

- **Lenient by default, strict when you want it.** Unrecognized values quietly
  become `False`, or raise on demand to catch typos in production config.
- **Always returns `bool`.** No `None`, no surprises in your type signatures.
- **Customizable value sets.** Replace or extend the truthy/falsy words your
  environment uses.
- **A CLI for shell scripts.** Exit codes map to truthiness, so it drops
  straight into `&&` / `||` chains.
- **Zero ceremony.** Zero dependencies, fully typed, Python 3.11+.

## Contents

- [Installation](#installation)
- [Usage](#usage)
- [Command-line interface](#command-line-interface)
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

### Snap

On Linux, the CLI is also available as a snap:

```bash
sudo snap install envbool
```

The snap is CLI-only; use `pip` or `uv` to `import envbool`. snapd overrides
`HOME`, `PATH`, `TMPDIR`, `XDG_RUNTIME_DIR`, and `SNAP_*`, so the CLI sees
snapd's values for those.

## Usage

### The basics

`envbool` is **lenient by default**: anything not recognized as truthy returns
`False`, and unset or empty variables return the default.

```python
from envbool import envbool

DEBUG = envbool("DEBUG")  # False if unset or empty
CACHE = envbool("CACHE", default=True)  # True if unset or empty
```

The built-in truthy values are `true`, `1`, `yes`, `on`; the falsy values are
`false`, `0`, `no`, `off`. Comparison is case-insensitive and ignores
surrounding whitespace.

### Strict mode

Pass `strict=True` to raise `InvalidBoolValueError` on anything outside the
truthy/falsy sets — ideal for failing fast on a misconfigured deployment.
Strict mode also raises `ConflictingValuesError` if the effective truthy and
falsy sets overlap (e.g. `extend_falsy={"on"}`), on every call, whatever the
value. Lenient mode instead logs a warning and lets truthy win.

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

Each set is built in order: start from the built-in set, swap it out if
`truthy`/`falsy` is given, then add anything in `extend_truthy`/
`extend_falsy`. Passing both `truthy` and `extend_truthy` therefore gives you
exactly their union:

```python
to_bool("y", truthy={"yes"}, extend_truthy={"y"})  # True
to_bool("true", truthy={"yes"}, extend_truthy={"y"})  # False: built-ins replaced
```

### Coercing arbitrary strings

Use `to_bool` for values that don't come from the environment. It accepts the
same keyword arguments as `envbool`.

```python
from envbool import to_bool

to_bool("yes")  # True
to_bool("0")  # False
to_bool("maybe", strict=True)  # raises InvalidBoolValueError
```

### Loading application settings

In a real application, read every flag once at startup into a single settings
object. With strict mode on, a typo like
`DEBUG=ture` stops startup instead of quietly reading as `False`:

```python
import sys
from dataclasses import dataclass

from envbool import EnvBoolError, envbool


@dataclass(frozen=True)
class Settings:
    debug: bool
    use_cache: bool
    new_checkout: bool
    send_emails: bool


def load_settings() -> Settings:
    return Settings(
        debug=envbool("DEBUG", strict=True),  # off unless set
        use_cache=envbool("USE_CACHE", default=True, strict=True),  # on unless set
        new_checkout=envbool("FEATURE_NEW_CHECKOUT", strict=True),
        send_emails=envbool("SEND_EMAILS", required=True, strict=True),  # must be set
    )


try:
    SETTINGS = load_settings()
except EnvBoolError as e:
    sys.exit(f"Invalid configuration: {e}")
```

Catching `EnvBoolError` covers every failure: a bad value, a missing
`required` variable, or overlapping value sets. The rest of the application
reads `SETTINGS.debug` and never touches `os.environ` again.

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
usage: envbool [-h] [--value TEXT] [--strict] [--warn] [--default]
               [--required] [--print] [--truthy VALUE] [--falsy VALUE]
               [--extend-truthy VALUE] [--extend-falsy VALUE]
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
  --required, -r        Exit 2 if VAR_NAME is not set in the environment.
  --print, -p           Print "true" or "false" instead of using exit codes.
  --truthy VALUE        Replace the truthy set with VALUE (repeatable).
  --falsy VALUE         Replace the falsy set with VALUE (repeatable).
  --extend-truthy VALUE
                        Add VALUE to the truthy set, after any --truthy
                        (repeatable).
  --extend-falsy VALUE  Add VALUE to the falsy set, after any --falsy
                        (repeatable).
```

A few rules worth knowing:

- Without `--strict` / `--warn`, coercion is lenient and logs no warnings.
- `VAR_NAME` and `--value` are mutually exclusive.
- `--required` only applies to `VAR_NAME`; combining it with `--value` or
  giving it no `VAR_NAME` at all is a usage error.
- With no `VAR_NAME`, `--value`, or non-empty piped stdin, the CLI prints
  usage and exits `2`.

### Scripts using `set -e`

Under `set -e` (errexit), a falsy result is a failing command: a bare
`envbool FLAG` on its own line aborts the script when the flag is off. Check
the status inside a condition instead, where errexit doesn't apply, or use
`--print` to get the answer as text:

```bash
set -e

envbool FLAG                  # aborts the script when FLAG is falsy

if envbool FLAG; then         # safe: the status is the condition
  echo "on"
fi

flag=$(envbool --print FLAG)  # safe: always exits 0 unless there's an error
```

`--print` still exits `2` on an error, so `set -e` catches a missing
`--required` variable or a bad value under `--strict`, while a falsy value
doesn't stop the script.

## API reference

| Symbol | Description |
| --- | --- |
| `envbool(var, **opts)` | Read an environment variable and return `bool`. |
| `to_bool(value, **opts)` | Coerce a string to `bool`. |
| `DEFAULT_TRUTHY` | `frozenset` of the built-in truthy strings. |
| `DEFAULT_FALSY` | `frozenset` of the built-in falsy strings. |
| `EnvBoolError` | Base class for every exception the library raises. |
| `InvalidBoolValueError` | Raised in strict mode for unrecognized values. Also a `ValueError`. |
| `ConflictingValuesError` | Raised in strict mode when the truthy and falsy sets overlap. Also a `ValueError`. |
| `MissingEnvVarError` | Raised by `envbool(required=True)` when the variable is unset. Also a `KeyError`. |

`envbool()` and `to_bool()` share the same keyword-only options:

| Option | Type | Default | Meaning |
| --- | --- | --- | --- |
| `default` | `bool` | `False` | Returned for unset/empty input. |
| `strict` | `bool` | `False` | Raise on unrecognized values. |
| `warn` | `bool` | `False` | Log a warning on unrecognized values. |
| `truthy` / `falsy` | `Iterable[str] \| None` | `None` | **Replace** the effective set. |
| `extend_truthy` / `extend_falsy` | `Iterable[str] \| None` | `None` | **Extend** the effective set, after any replacement. |

`envbool()` also accepts `required` (`bool`, default `False`): when `True`, a
variable that is unset raises `MissingEnvVarError` before `default` is applied. A
variable set to an empty string counts as present and still uses `default`.

## Advanced topics

### Exception handling

Every exception inherits from `EnvBoolError`, so a single `except EnvBoolError`
catches the whole library. Catch a specific subclass when you need its detail:

```python
from envbool import envbool, InvalidBoolValueError

try:
    result = envbool("MY_VAR", strict=True)
except InvalidBoolValueError as e:
    print(e.var)  # "MY_VAR" — env var name, or None when raised from to_bool()
    print(e.value)  # "maybe" — the normalized (stripped, lowercased) value
    print(e.truthy)  # frozenset({"true", "1", "yes", "on"}) — effective truthy set
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
| `WARNING` | An unrecognized value fell through in lenient mode (only when `warn=True`). |
| `WARNING` | The truthy and falsy sets overlap in lenient mode (truthy wins; strict mode raises `ConflictingValuesError` instead). |

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

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup, project layout, and the conventions this repo follows.

## License

Released under the [MIT License](LICENSE).
