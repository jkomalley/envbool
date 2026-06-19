# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jkomalley/envbool/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jkomalley/envbool/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/jkomalley/envbool/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jkomalley/envbool/releases/tag/v0.1.0
