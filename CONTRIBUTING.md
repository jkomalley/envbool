# Contributing to envbool

This document covers two audiences: **library consumers** who need advanced usage details not in the README, and **contributors** who want to develop or improve envbool.

---

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

All envbool exceptions inherit from `EnvBoolError`, so you can catch the whole library in one place:

```python
from envbool import EnvBoolError

try:
    result = envbool("MY_VAR", strict=True)
except EnvBoolError:
    ...
```

For finer-grained handling:

**`InvalidBoolValueError`** is raised in strict mode when a value is not in the truthy or falsy sets. It also inherits from `ValueError`, so existing `except ValueError` handlers continue to work without changes.

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

The exception message includes the full expected sets for easy debugging:

```
InvalidBoolValueError: Invalid boolean value for MY_VAR: 'maybe'
  Expected truthy: 1, on, true, yes
  Expected falsy:  0, false, no, off
```

**`ConfigError`** is raised when a config file is found but malformed or contains wrong value types (e.g. `strict = "yes"` instead of `strict = true`). It carries the file path:

```python
from envbool import ConfigError, load_config

try:
    load_config()
except ConfigError as e:
    print(e.path)  # Path to the problematic file
```

### Logging

envbool uses Python's standard `logging` module with a namespaced logger. No handlers are attached — the library follows the convention of letting the application configure logging.

To see envbool log output in your application:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or target just the envbool logger:

```python
import logging
logging.getLogger("envbool").setLevel(logging.DEBUG)
logging.getLogger("envbool").addHandler(logging.StreamHandler())
```

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

### CLI: coercing a literal string

The `--value` flag lets you coerce a string directly without reading an environment variable. This is useful for testing value sets or scripting:

```bash
# Coerce a literal string
envbool --value "yes" && echo "truthy"
envbool --value "maybe" --strict || echo "unrecognized"

# Equivalent: pipe from stdin
echo "yes" | envbool && echo "truthy"
```

`--value` and a `VAR_NAME` argument are mutually exclusive.

---

## Development setup

**Prerequisites:** Python 3.11+, [`uv`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/jkomalley/envbool.git
cd envbool
uv sync
uv run pre-commit install
```

### Running checks

The project uses [`just`](https://github.com/casey/just) as a task runner:

```
just            # format + lint + typecheck + test (run all)
just test       # uv run pytest
just cov        # uv run pytest --cov=envbool
just lint       # uv run ruff check src/ tests/
just format     # uv run ruff format src/ tests/
just typecheck  # uv run ty check src/
```

Or run the commands directly without `just`.

### Testing notes

- Config tests must use `tmp_path` and `monkeypatch.chdir()` for directory isolation.
- `to_bool()` tests must not touch `os.environ` — `envbool()` tests use `monkeypatch.setenv` / `delenv`.
- Every test needs a clean config cache. The project's `conftest.py` already installs an autouse `_reset_envbool_config` fixture that calls `_reset_config()` after each test.

---

## Submitting changes

- Open an issue before starting large or behavior-changing work.
- PRs should include tests for any new behavior and pass `just all` cleanly.
