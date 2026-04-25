# envbool — Design Document

## Overview

`envbool` is a small Python library and CLI tool for coercing environment variables (and arbitrary strings) into boolean values. One dependency (`platformdirs`), Python 3.11+.

The core problem: every project ends up with ad-hoc `os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")` scattered everywhere. `envbool` provides a single, well-tested function that handles the common cases and lets you configure the edge cases.

---

## Design Decisions

- **Lenient by default.** The default mode checks the input against a set of known truthy values. Anything else — including unset variables, empty strings, and unrecognized values — returns `False`. This covers 90% of real usage with zero configuration.
- **Strict mode is opt-in.** When enabled, the input is checked against both a truthy and a falsy set. Anything outside either set raises an `InvalidBoolValueError`. This is for situations where you want to catch misconfigurations (e.g. `ENABLE_CACHE=trie` in production).
- **The falsy set only exists to serve strict mode.** In lenient mode, it's never consulted.
- **Minimal dependencies.** The only runtime dependency is `platformdirs` for cross-platform config file location. The core logic is all stdlib — `tomllib` for config parsing, `argparse` for CLI, string operations for coercion.
- **Empty string and unset variables are treated the same.** Both return `False` by default (or whatever `default` is set to). Most deployment tools can't meaningfully distinguish between `VAR=` and not setting `VAR` at all.
- **Return type is always `bool`.** No `None` returns — keeps the API simple and the type signature clean. Trade-off: callers cannot distinguish "variable was explicitly set to a falsy value" from "variable was not set at all." This is acknowledged as a deliberate simplification — applications that need tri-state detection can check `os.environ` directly before calling `envbool`. This trade-off should be documented in the README.

---

## Error Handling

### Custom exception hierarchy

`envbool` uses a custom exception hierarchy rooted in a base class. This lets users catch all `envbool` errors broadly or handle specific cases.

```python
class EnvBoolError(Exception):
    """Base exception for all envbool errors."""

class InvalidBoolValueError(EnvBoolError, ValueError):
    """Raised in strict mode when a value isn't in the truthy or falsy sets.

    Inherits from both EnvBoolError and ValueError so that existing
    code catching ValueError still works.
    """
    var: str | None    # env var name if from envbool(), None if from to_bool()
    value: str         # the unrecognized value
    truthy: frozenset[str]  # the effective truthy set
    falsy: frozenset[str]   # the effective falsy set

class ConfigError(EnvBoolError):
    """Raised when a config file is malformed or contains invalid values."""
    path: Path         # path to the problematic config file
```

The `InvalidBoolValueError` inherits from both `EnvBoolError` and `ValueError`. This is intentional — anyone already catching `ValueError` won't break, but users who want finer-grained control can catch `InvalidBoolValueError` specifically. The exception carries context attributes so error handlers can inspect what went wrong.

Error message format:

```
InvalidBoolValueError: Invalid boolean value for ENABLE_CACHE: 'maybe'
  Expected truthy: true, 1, yes, on
  Expected falsy:  false, 0, no, off
```

### Edge case handling

- **`truthy=set()`** (empty set) — allowed but means nothing is truthy. Combined with strict mode and an empty falsy set, everything raises. This is a valid (if unusual) configuration.
- **Overlapping truthy/falsy sets** — if a value appears in both sets, truthy wins (checked first). A `WARNING`-level log is emitted noting the overlap.
- **Config file is malformed TOML** — raises `ConfigError` with the file path and the underlying parse error.
- **Config file has unexpected keys** — ignored silently. This lets config files be forward-compatible if new options are added later.
- **Config file has wrong value types** (e.g. `strict = "yes"` instead of `strict = true`) — raises `ConfigError` with a helpful message about the expected type.
- **`platformdirs` can't determine config dir** — falls back to no user-level config. Should never happen in practice but the code doesn't crash if it does.

---

## Thread Safety

The config cache uses double-checked locking to ensure safe concurrent initialization without unnecessary overhead. On first call to `envbool()` or `to_bool()`, the config is loaded from disk and stored in a module-level variable. The lock prevents duplicate disk I/O if multiple threads race on the first call.

After the first load, all subsequent calls check the cached value without acquiring the lock — no contention in the hot path. The `envbool()` and `to_bool()` functions themselves are stateless beyond the config cache, so they're inherently thread-safe.

```python
import threading

_config: EnvBoolConfig | None = None
_config_lock = threading.Lock()

def _get_config() -> EnvBoolConfig:
    global _config
    if _config is not None:
        return _config
    with _config_lock:
        if _config is not None:  # double-check after acquiring lock
            return _config
        _config = _load_config_from_disk()
        return _config
```

### Testing support: `_reset_config()`

Because the config is cached globally, tests that need to verify behavior under different configurations would read stale state. A private `_reset_config()` function clears the cache, intended for use in test fixtures:

```python
def _reset_config() -> None:
    """Clear the cached config. For testing only."""
    global _config
    with _config_lock:
        _config = None
```

This is underscore-prefixed to signal it's not part of the public API. Document a recommended pytest fixture pattern for users:

```python
# conftest.py
import pytest
from envbool._config import _reset_config

@pytest.fixture(autouse=True)
def reset_envbool_config():
    yield
    _reset_config()
```

---

## Logging

`envbool` uses Python's stdlib `logging` module with a namespaced logger (`logging.getLogger("envbool")`). By default, no handlers are attached — the library follows the best practice of letting the application configure logging.

### What gets logged

| Level | When |
|-------|------|
| `DEBUG` | Config file found and loaded from path X |
| `DEBUG` | No config file found, using defaults |
| `DEBUG` | Effective truthy/falsy sets after resolution |
| `WARNING` | Lenient mode: unrecognized value fell back to default (only when `warn=True`) |
| `WARNING` | Overlapping values in truthy and falsy sets |

### The `warn` parameter

In lenient mode, unrecognized values silently return `False`. For debugging, a `warn` parameter emits a log warning:

```python
# Silent (default — defers to config file, or False if no config)
envbool("FLAG")

# Explicitly enable warnings (overrides config file)
envbool("FLAG", warn=True)

# Explicitly disable warnings (overrides config file)
envbool("FLAG", warn=False)
```

The `warn` parameter uses three-state logic: `None` (the default) means "use whatever the config file says, or `False` if there's no config." `True` or `False` override the config file setting. The `strict` parameter uses the same pattern — `None` defers to config, `True`/`False` override.

This is also configurable in the config file:

```toml
warn = true   # emit warnings for unrecognized values in lenient mode
```

The `warn` parameter is only meaningful in lenient mode. In strict mode, unrecognized values raise an exception regardless.

The function-level `warn` argument overrides the config file setting, consistent with the overall precedence model.

---

## Default Value Sets

### Truthy (ships with library, used in all modes)

```
"true", "1", "yes", "on"
```

### Falsy (ships with library, only used in strict mode)

```
"false", "0", "no", "off"
```

All comparisons are case-insensitive and stripped of leading/trailing whitespace.

These sets are intentionally small. Values like `"enabled"`, `"disabled"`, `"y"`, `"n"` are left out of the defaults to avoid surprising behavior, but users can add them via custom value sets.

---

## Custom Value Sets: Extend vs Replace

Inspired by ruff's `select` / `extend-select` pattern for rule selection, custom value sets support two modes:

- **`truthy` / `falsy`** — **replaces** the default set entirely. Use when you want full control over what's accepted.
- **`extend_truthy` / `extend_falsy`** — **adds to** the default set. Use when the defaults are fine but you need a few extras.

If both `truthy` and `extend_truthy` are provided, `truthy` takes priority and `extend_truthy` is ignored (same as ruff's behavior — `select` overrides `extend-select`).

```python
# Replace: only these values are truthy, defaults are gone
envbool("FLAG", truthy={"si", "oui", "ja"})

# Extend: defaults + these additional values
envbool("FLAG", extend_truthy={"enabled", "y"})
# Effective truthy set: {"true", "1", "yes", "on", "enabled", "y"}

# Replace takes priority if both are provided
envbool("FLAG", truthy={"1"}, extend_truthy={"enabled"})
# Effective truthy set: {"1"} — extend is ignored
```

The same pattern applies to `falsy` / `extend_falsy`, which only matter in strict mode.

### Set resolution logic

Resolution happens in two phases: first the config file is applied to the hardcoded defaults, then function arguments override the result.

```
# Phase 1: config file layer (computed once at config load time)
if config.truthy is provided:
    config_truthy = config.truthy
elif config.extend_truthy is provided:
    config_truthy = DEFAULT_TRUTHY | config.extend_truthy
else:
    config_truthy = DEFAULT_TRUTHY

# Phase 2: function argument layer (computed per-call)
if truthy arg is provided:
    effective_truthy = truthy arg
elif extend_truthy arg is provided:
    effective_truthy = config_truthy | extend_truthy arg
else:
    effective_truthy = config_truthy

(same for falsy / extend_falsy)
```

This means function-level `extend_truthy` extends the config-resolved set, not just the hardcoded defaults. If your config adds `"enabled"` and your function call adds `"y"`, you get both.

---

## Library API

### `envbool` — read a boolean from an environment variable

```python
from envbool import envbool

# Basic usage — False if unset or empty
DEBUG = envbool("DEBUG")

# Custom default for unset/empty
VERBOSE = envbool("VERBOSE", default=True)

# Strict mode — raises InvalidBoolValueError on unrecognized values
STRICT = envbool("STRICT_MODE", strict=True)

# Extend defaults with extra truthy values
FEATURE = envbool("FEATURE_FLAG", extend_truthy={"enabled", "y"})

# Replace defaults entirely
LEGACY = envbool("LEGACY_FLAG", truthy={"1"})

# Strict mode with extended falsy set
CACHE = envbool(
    "ENABLE_CACHE",
    strict=True,
    extend_truthy={"enabled"},
    extend_falsy={"disabled"},
)
```

**Signature:**

```python
from collections.abc import Iterable

def envbool(
    var: str,
    *,
    default: bool = False,
    strict: bool | None = None,
    warn: bool | None = None,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> bool:
```

Custom value sets accept any `Iterable[str]` — sets, lists, tuples all work. Internally, inputs are cast to `frozenset` for fast, immutable lookups.

**Behavior:**

1. Resolve effective truthy/falsy sets (see set resolution logic above)
2. Resolve `strict`: if `None`, use config file value (or `False` if no config)
3. Resolve `warn`: if `None`, use config file value (or `False` if no config)
4. Read `os.environ.get(var)`
5. If the value is `None` (unset) or `""` (empty), return `default`
6. Strip whitespace, lowercase the value
7. If value is in the effective truthy set → return `True`
8. If effective `strict` is `True` and value is not in the effective falsy set → raise `InvalidBoolValueError`
9. If effective `warn` is `True`, log a warning about the unrecognized value
10. Return `False`

**Error messages in strict mode:**

```
envbool.InvalidBoolValueError: Invalid boolean value for ENV_VAR: 'maybe'
  Expected truthy: true, 1, yes, on
  Expected falsy:  false, 0, no, off
```

The error message lists the full effective sets (including any extensions) so the user can see exactly what's accepted.

### `to_bool` — coerce an arbitrary string (no env var lookup)

```python
from envbool import to_bool

to_bool("yes")      # True
to_bool("0")        # False
to_bool("")         # False
to_bool("maybe")    # False (lenient)
to_bool("maybe", strict=True)  # raises InvalidBoolValueError
to_bool("enabled", extend_truthy={"enabled"})  # True
```

**Signature** (same `Iterable[str]` types as `envbool`)**:**

```python
def to_bool(
    value: str,
    *,
    default: bool = False,
    strict: bool | None = None,
    warn: bool | None = None,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    extend_truthy: Iterable[str] | None = None,
    extend_falsy: Iterable[str] | None = None,
) -> bool:
```

Same logic as `envbool` but takes a string directly instead of an env var name. `envbool` is essentially `to_bool(os.environ.get(var, ""))` with the unset case handled.

This is the function that makes the library useful beyond just env vars — anywhere you're coercing user input strings to bools.

### Exported constants

The default sets are exported so users can reference or inspect them:

```python
from envbool import DEFAULT_TRUTHY, DEFAULT_FALSY

print(DEFAULT_TRUTHY)  # frozenset({"true", "1", "yes", "on"})
print(DEFAULT_FALSY)   # frozenset({"false", "0", "no", "off"})
```

These are `frozenset` to prevent accidental mutation.

---

## Config File

A TOML config file provides project-level or user-level defaults for custom value sets and strict mode. This avoids repeating `extend_truthy={"enabled"}` on every call.

### Location

Config file discovery uses `platformdirs` and follows a priority order (first found wins):

1. **Project-level:** `./envbool.toml` or `./pyproject.toml` (under `[tool.envbool]`)
2. **User-level:** `<platformdirs.user_config_dir>/envbool/config.toml`

Project-level config lets teams share settings via version control. User-level config is for personal defaults that apply everywhere.

### Format

```toml
# envbool.toml (standalone) or [tool.envbool] in pyproject.toml

strict = false               # default mode for all calls
warn = false                 # log warnings for unrecognized values in lenient mode

truthy = ["1", "yes"]        # replaces default truthy set
# OR
extend_truthy = ["enabled", "y", "si"]  # adds to default truthy set

falsy = ["0", "no"]          # replaces default falsy set (strict mode only)
# OR
extend_falsy = ["disabled", "n"]        # adds to default falsy set
```

Same extend/replace semantics as the function arguments — `truthy` overrides `extend_truthy` if both are present.

### Discovery details

**Project-level search:** `envbool` walks up the directory tree from the current working directory, looking for config files at each level (similar to how ruff, mypy, and pytest discover config). It stops at the first directory that contains a match. Within a directory, the search order is:

1. `envbool.toml` (standalone, takes priority)
2. `pyproject.toml` under `[tool.envbool]`

If both exist in the same directory, `envbool.toml` wins and `pyproject.toml` is not consulted.

The walk stops at the filesystem root or at common project boundary markers (`.git`, `.hg`, `setup.py`, `setup.cfg`). A `pyproject.toml` also acts as a boundary marker — but unlike the others, it's checked for a `[tool.envbool]` section before the walk stops. If it has the section, it's used as the config. If it doesn't, the walk still stops there (you've reached the project root, there's just no `envbool` config in it). As a safety net, traversal is also capped at 10 directory levels — in deeply nested CI/CD environments or Docker containers without boundary markers, this prevents walking all the way to `/`.

**Escape hatch:** Setting the environment variable `ENVBOOL_NO_CONFIG=1` skips all config file discovery and uses hardcoded defaults only. This is useful for CI pipelines, Docker containers, or any context where deterministic behavior is required regardless of what config files might exist on disk. This check uses a raw `os.environ.get()` — not `envbool` itself — to avoid circular dependency during initialization.

**User-level search:** `<platformdirs.user_config_dir("envbool")>/config.toml`

**Overall priority:** project-level > user-level. If a project-level config is found, the user-level config is not consulted. This keeps behavior simple and debuggable — there's always at most one active config file.

### Precedence

Function arguments always override the config file. The layering is:

```
defaults (hardcoded) → config file → function arguments
```

So if the config file sets `extend_truthy = ["enabled"]` and you call `envbool("FLAG", truthy={"1"})`, the function argument wins and only `"1"` is truthy.

If the config file sets `strict = true`, calling `envbool("FLAG")` (without passing `strict`) defers to the config — strict mode is active. Calling `envbool("FLAG", strict=False)` explicitly overrides the config. The same applies to `warn`.

### Config loading

The config is loaded **once** on first use and cached for the lifetime of the process. It's not reloaded per-call. This keeps things fast and predictable.

A `load_config()` function is exposed for users who want to inspect or preload the config:

```python
from envbool import load_config

config = load_config()
print(config.strict)           # bool
print(config.effective_truthy) # frozenset
```

The returned `EnvBoolConfig` is a frozen dataclass:

```python
@dataclass(frozen=True)
class EnvBoolConfig:
    strict: bool = False
    warn: bool = False
    effective_truthy: frozenset[str] = DEFAULT_TRUTHY
    effective_falsy: frozenset[str] = DEFAULT_FALSY
    source_path: Path | None = None  # which file was loaded, None if defaults
```

`effective_truthy` and `effective_falsy` are the fully resolved sets after applying extend/replace logic from the config file. `source_path` tells you which file the config came from (useful for debugging).

### When no config file exists

Everything works exactly as if the config file contained no overrides. The hardcoded defaults apply. The config file is entirely optional — most users will never create one.

---

## CLI

The CLI serves two purposes: quick shell script usage and piped input processing.

### Read an env var

```bash
# Exit code 0 if truthy, 1 if falsy
envbool DEBUG && echo "debug is on"

# With strict mode
envbool --strict ENABLE_CACHE || echo "cache is off"
```

### Coerce a string directly

```bash
# Pass a value directly
envbool --value "yes" && echo "truthy"

# Pipe input
echo "true" | envbool && echo "truthy"
```

**Stdin handling:** When reading from stdin, the CLI uses `sys.stdin.read().strip()` to handle trailing newlines and whitespace. Multi-line input is rejected with an error (exit code 2) — only a single value is accepted.

### Print the resolved value

```bash
# Instead of exit codes, print true/false
envbool --print DEBUG
# → "true" or "false"
```

### CLI flags

```
envbool [OPTIONS] [VAR_NAME]

Arguments:
  VAR_NAME              Environment variable name to check

Options:
  --value, -v TEXT      Check a literal string instead of an env var
  --strict, -s          Raise error on unrecognized values
  --default, -d         Default if unset/empty (default: false)
  --print, -p           Print "true"/"false" instead of using exit codes
  --help, -h            Show help
```

**Exit codes:**
- `0` — value is truthy
- `1` — value is falsy (or unset/empty)
- `2` — error (strict mode violation, bad arguments)

---

## Module Layout

All implementation modules are private (underscore-prefixed). Users interact exclusively through `__init__.py`. `exceptions.py` is the only public submodule — kept importable by name so downstream `except` clauses can reference specific exception types without going through the top-level package.

```
src/envbool/
├── __init__.py       # Public API: envbool, to_bool, load_config, EnvBoolConfig,
│                     #   DEFAULT_TRUTHY, DEFAULT_FALSY
├── py.typed          # PEP 561 marker
├── exceptions.py     # Public: EnvBoolError, InvalidBoolValueError, ConfigError
├── _defaults.py      # DEFAULT_TRUTHY, DEFAULT_FALSY (shared by _core and _config
│                     #   to avoid a circular import)
├── _core.py          # Core coercion logic: to_bool, _resolve, default sets
├── _env.py           # envbool() — env var reading + delegation to _core
├── _config.py        # Config file discovery, loading, caching (thread-safe),
│                     #   EnvBoolConfig dataclass, _reset_config()
└── _cli.py           # CLI entry point (argparse)
```

The split between `_core.py` and `_env.py` keeps the string coercion logic independent of `os.environ`, making `to_bool` easy to test without mocking environment variables.

`_defaults.py` holds `DEFAULT_TRUTHY` and `DEFAULT_FALSY` as the single source of truth. Both `_core.py` and `_config.py` import from it; without this module, `_core.py` importing `_config.py` and `_config.py` importing `_core.py` would create a circular dependency.

`_config.py` handles discovery (project → user), TOML parsing via `tomllib`, thread-safe caching via double-checked locking, validation, and the `EnvBoolConfig` frozen dataclass. Also exposes `_reset_config()` for test teardown.

`exceptions.py` defines the exception hierarchy. Kept as a public module so users can write `from envbool.exceptions import InvalidBoolValueError` in `except` clauses without pulling in the rest of the library.

`_cli.py` uses `argparse` (stdlib) and delegates to `envbool()` / `to_bool()`.

---

## Project Setup

- `src` layout with `uv`
- `uv_build` build backend (zero-config for pure Python src layout)
- `ruff` for linting/formatting
- `ty` for type checking
- `pytest` for testing
- Runtime dependency: `platformdirs`
- `[project.scripts]` entry point for the CLI: `envbool = "envbool.cli:main"`

---

## Test Strategy

### Core (`to_bool`)

- Each default truthy value returns `True` (case variations: `"TRUE"`, `"True"`, `"true"`, `" true "`)
- Each default falsy value returns `False` in both modes
- Empty string returns `default`
- Unrecognized value returns `False` in lenient mode
- Unrecognized value raises `InvalidBoolValueError` in strict mode
- Error exception carries `value`, `truthy`, and `falsy` attributes
- Error inherits from both `EnvBoolError` and `ValueError`
- Whitespace stripping works
- `truthy` replaces the default truthy set
- `extend_truthy` adds to the default truthy set
- `truthy` takes priority over `extend_truthy` when both are provided
- Same replacement/extension behavior for `falsy` / `extend_falsy`
- Empty `truthy=set()` is allowed (nothing is truthy)
- Overlapping truthy/falsy sets: truthy wins
- Accepts lists, tuples, and sets for custom value set params (Iterable[str])
- `strict=None` defaults to `False` when no config file exists
- `warn=None` defaults to `False` when no config file exists

### Env var (`envbool`)

- Reads from `os.environ` (use `monkeypatch` or `os.environ` dict manipulation)
- Unset variable returns `default`
- Set variable delegates to `to_bool` correctly
- All `to_bool` behaviors apply through `envbool`
- `InvalidBoolValueError.var` is populated with the env var name

### Config file

- Discovers `envbool.toml` walking up directory tree
- Discovers `[tool.envbool]` in `pyproject.toml` walking up
- Stops walking at boundary markers (`.git`, `.hg`, `setup.py`, `setup.cfg`)
- `pyproject.toml` acts as boundary but is checked for `[tool.envbool]` before stopping
- `pyproject.toml` without `[tool.envbool]` still stops the walk (project root, no config)
- Stops walking after 10 directory levels
- `ENVBOOL_NO_CONFIG=1` skips all config discovery (raw `os.environ` check)
- `envbool.toml` takes priority over `pyproject.toml` in same directory
- Discovers user-level config via `platformdirs`
- Project-level takes priority over user-level (user config ignored if project found)
- `truthy` in config replaces defaults
- `extend_truthy` in config extends defaults
- `warn` in config propagates to calls when function arg is `None`
- `strict` in config propagates to calls when function arg is `None`
- `strict=True` at function level overrides config `strict = false`
- `strict=False` at function level overrides config `strict = true`
- Same override behavior for `warn`
- Function arguments override config file settings
- Function-level `extend_truthy` extends the config-resolved set, not just hardcoded defaults
- `load_config()` returns `EnvBoolConfig` with correct fields and `source_path`
- Config is loaded once and cached (double-checked locking)
- Concurrent first-access: lock prevents duplicate disk I/O
- `_reset_config()` clears the cache for testing
- Missing config file works fine (defaults apply, `source_path` is `None`)
- Malformed TOML raises `ConfigError` with file path
- Wrong value types in config raises `ConfigError`
- Unknown keys in config are silently ignored

### Testability

- `_reset_config()` clears global config cache between tests
- Autouse fixture pattern documented for users
- Config tests use `tmp_path` and `monkeypatch.chdir()` for isolation
- Each test starts with a clean config state

### Logging

- `warn=True` emits `WARNING` for unrecognized values in lenient mode
- `warn=False` suppresses warnings regardless of config
- `warn=None` (default) defers to config file setting
- Config-level `warn` setting works when function arg is `None`
- Function-level `warn` overrides config-level
- Overlapping truthy/falsy sets emit a `WARNING`
- Config loading emits `DEBUG` messages

### CLI

- Exit code 0 for truthy env var
- Exit code 1 for falsy/unset env var
- Exit code 2 for strict mode violation
- `--value` flag works without env var
- `--print` outputs "true" / "false" to stdout
- Stdin piping works (strips whitespace)
- Stdin rejects multi-line input with exit code 2
- `--strict` flag propagates
- `--default` flag works
- CLI respects config file settings
- Strict mode errors print to stderr with exit code 2

---

## README Outline

The README is the primary documentation for a published library. It should cover:

1. **One-liner + badges** — what it is, PyPI version, Python versions, license
2. **Install** — `pip install envbool` / `uv add envbool`
3. **Quick start** — 5-line example showing the most common usage
4. **Library API** — `envbool()`, `to_bool()`, parameters, return values
5. **Strict mode** — what it is, when to use it, error format
6. **Custom value sets** — extend vs replace, examples
7. **Config file** — format, discovery, precedence
8. **CLI usage** — examples for shell scripts, exit codes, flags
9. **Default value sets** — the full truthy/falsy lists
10. **Exceptions** — `InvalidBoolValueError`, `ConfigError`, catching patterns
11. **Logging** — how to enable, what gets logged, `warn` parameter
12. **Prior art / why this exists** — brief comparison with env-flag, environs, etc.
13. **Contributing** — link to issues, dev setup (`uv sync`, `ruff`, `pytest`)
14. **License** — MIT

---

## Prior Art

- **truthyenv** — Author's own earlier attempt at this problem (github.com/jkomalley/truthyenv). Unfinished; `envbool` is a ground-up redesign with a more complete feature set.
- **env-flag** — Closest existing library. Truthy set only, returns `False` for everything else. No strict mode, no CLI, no custom value sets. Last updated 2019.
- **environs** — Full env parsing framework with `env.bool()`. Depends on marshmallow, includes Django integrations, URL parsing. Much heavier, different scope.
- **envparse** — General env var parsing with `cast=bool`. Similar to environs in scope.
- **python-env-utils** — Basic type coercion helpers including bool. Minimal, Python 2 era.
- **Zod `z.envbool()`** — TypeScript/Zod is actively adding this. Strict by default, larger default sets (includes `"y"`, `"n"`, `"enabled"`, `"disabled"`), custom truthy/falsy via options. Different language but validates the concept.

`envbool` differentiates by being: focused (bool only, not a general env parser), modern (Python 3.11+, typed, `py.typed`), configurable (extend/replace pattern for value sets, strict/lenient modes, TOML config file), and practical (CLI tool for shell scripts).

---

## Open Questions

None — all resolved during design. Key decisions made:

- Lenient by default, strict opt-in
- `truthy` replaces, `extend_truthy` extends (ruff pattern)
- Function-level `extend_truthy` extends the config-resolved set, not just hardcoded defaults
- Empty string / unset → `False` (configurable via `default`)
- `to_bool("")` and `envbool("UNSET")` both use the `default` parameter
- Return type always `bool`, no `None` (tri-state trade-off documented in README)
- Custom value set params accept `Iterable[str]`, cast to `frozenset` internally
- Custom exception hierarchy: `EnvBoolError` → `InvalidBoolValueError`, `ConfigError`
- `InvalidBoolValueError` inherits from both `EnvBoolError` and `ValueError`
- `EnvBoolConfig` frozen dataclass with `source_path` for debugging
- Double-checked locking for thread-safe config cache
- `_reset_config()` exposed for test fixture teardown
- `warn: bool | None = None` — `None` defers to config, `True`/`False` override
- `strict: bool | None = None` — same three-state pattern as `warn`
- One dependency: `platformdirs`
- TOML config file with directory tree walking (capped at 10 levels) for project-level discovery
- `pyproject.toml` is both a boundary marker and a config source (checked before stopping)
- `ENVBOOL_NO_CONFIG=1` escape hatch via raw `os.environ` (avoids circular dependency)
- `envbool.toml` takes priority over `pyproject.toml` at same level
- Project-level config wins entirely over user-level (no merging)
- Config file settings are overridden by function arguments
- Unknown config keys are silently ignored (forward-compatible)
- CLI stdin reads `.strip()`, rejects multi-line input
- Name `envbool` is available on PyPI
