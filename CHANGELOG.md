# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-12

### Removed (breaking)

- Config file discovery: `envbool.toml`, `[tool.envbool]` in `pyproject.toml`,
  and the user-level `config.toml` fallback. File discovery made `to_bool()`
  non-deterministic across launch directories, added hidden filesystem I/O to
  a pure-looking call, and let any ancestor directory's config silently
  redefine truthy/falsy semantics for a process that never opted in.
- `ConfigError`, `--show-config`, `reload_config()`, `ENVBOOL_NO_CONFIG`.
- `EnvBoolConfig` and `load_config()` — replaced by `Defaults` and
  `get_defaults()` (see Added, below).
- The `platformdirs` runtime dependency. `envbool` is now zero-dependency.

### Added

- `set_defaults(**opts)`: set process-level `strict` / `warn` / `truthy` /
  `falsy` / `extend_truthy` / `extend_falsy` defaults once at application
  startup — in-memory, no disk I/O. Replaces config files as the way to share
  policy across call sites. Each call rebuilds from the built-ins (it does
  not merge with a previous call).
- `get_defaults()`: inspect the active `Defaults`.
- `reset_defaults()`: restore built-in defaults (for test fixtures).
- `Defaults`: frozen dataclass returned by `get_defaults()`.

### Fixed

- `MissingEnvVarError.__str__` no longer wraps its message in stray quotes
  (an artifact of inheriting from `KeyError`).
- `--required` now rejects usage when there's no `VAR_NAME` to require
  (previously silently ignored on the stdin and `--show-config` paths).
- Empty non-TTY stdin (e.g. `envbool </dev/null` with a forgotten `VAR_NAME`
  under cron/CI) now prints usage and exits `2`, instead of silently coercing
  `""` to `default` and exiting `1`.

### Migration

Delete any `envbool.toml` file or `[tool.envbool]` section and call
`set_defaults()` once at application startup instead:

```toml
# envbool.toml (delete this file)
strict = true
extend_truthy = ["enabled"]
```

```python
# equivalent, at application startup
import envbool
envbool.set_defaults(strict=True, extend_truthy=["enabled"])
```

`ENVBOOL_NO_CONFIG=1` is no longer needed and no longer does anything —
there is no config discovery left to disable.

## [0.3.0] - 2026-06-18

### Added

- `reload_config()`: a public function that discards the cached config and
  re-reads the config file, for long-running processes that change config at
  runtime.
- `required` option on `envbool()` (and `--required` / `-r` on the CLI): raise
  the new `MissingEnvVarError` when a variable is unset. A variable set to an
  empty string counts as present and still uses `default`.
- `python -m envbool` now works as an alias for the installed `envbool` command.

## [0.2.0] - 2026-06-18

First feature release since 0.1.1, adding several CLI capabilities alongside a
bug fix and a full documentation overhaul.

> This release supersedes 0.1.2, which was published as a patch by mistake
> (it shipped new features, so it should have been a minor bump). 0.1.2 has
> been retracted — use 0.2.0.

### Added

- Custom value sets on the CLI: `--truthy` / `--falsy` (replace) and
  `--extend-truthy` / `--extend-falsy` (extend), mirroring the library API and
  ruff's select/extend-select pattern.
- `--show-config`: print the effective configuration (config file path,
  `strict`, `warn`, and the resolved truthy/falsy sets) and exit. Combine it
  with the value-set flags to preview overrides.
- `--warn`: log a warning when a value isn't recognized in lenient mode, without
  failing — useful while migrating toward `--strict`.

### Fixed

- A malformed config file on the CLI now produces a clean `error: ...` message
  and exit code `2`, instead of crashing with an uncaught `ConfigError`
  traceback.

### Changed

- Rewrote the README and CONTRIBUTING for clearer structure, real terminal-session
  CLI examples, a typed options table, and contributor onboarding. Corrected the
  documented user-config path on macOS.
- Internal: deduplicated the value-set resolution helpers and removed redundant
  test fixtures.

## [0.1.1] - 2026-04-25

### Changed

- Fixed the license badge in the README (switched to the GitHub endpoint, which
  correctly handles [PEP 639](https://peps.python.org/pep-0639/) license
  expressions).
- Added `keywords` and `[project.urls]` (Homepage, Repository, Issues,
  Changelog) to `pyproject.toml` so PyPI displays sidebar links.
- Bumped dev dependencies: `ruff` 0.15.12, `ty` 0.0.32, `pre-commit` 4.6.0.

No functional changes to the library or CLI.

## [0.1.0] - 2026-04-25

Initial release.

### Added

- `envbool(var)`: read an environment variable and return a `bool`.
- `to_bool(value)`: coerce an arbitrary string to `bool`.
- Strict mode via `strict=True`, raising `InvalidBoolValueError` on unrecognized
  values.
- Customizable value sets via `truthy` / `falsy` / `extend_truthy` /
  `extend_falsy`.
- CLI with exit-code semantics (`0` truthy, `1` falsy) and a `--print` flag.
- TOML config support (`envbool.toml` or `[tool.envbool]` in `pyproject.toml`).

[0.4.0]: https://github.com/jkomalley/envbool/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jkomalley/envbool/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jkomalley/envbool/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/jkomalley/envbool/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jkomalley/envbool/releases/tag/v0.1.0
