# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`envbool` is a Python library and CLI tool for coercing environment variables and arbitrary strings into boolean values. Python 3.11+, src layout, managed with `uv`.

## Commands

- **Install deps:** `uv sync`
- **Run tests:** `uv run pytest`
- **Run single test:** `uv run pytest tests/test_core.py::test_name -v`
- **Test with coverage:** `uv run pytest --cov=envbool`
- **Lint:** `uv run ruff check src/ tests/`
- **Format:** `uv run ruff format src/ tests/`
- **Type check:** `uv run ty check src/`

## Architecture

The project uses a `src/envbool/` layout with this module structure:

- `core.py` — Pure string coercion logic (`to_bool`, set resolution, default sets). No `os.environ` dependency.
- `env.py` — `envbool()` function: reads env vars, delegates to `core.py`.
- `config.py` — Config file discovery (project-level walking up dirs, user-level via `platformdirs`), TOML parsing, thread-safe caching with double-checked locking, `EnvBoolConfig` frozen dataclass, `_reset_config()`.
- `exceptions.py` — `EnvBoolError` base, `InvalidBoolValueError(EnvBoolError, ValueError)`, `ConfigError(EnvBoolError)`.
- `cli.py` — CLI entry point using `argparse`.
- `__init__.py` — Public API re-exports.

Key design patterns:
- **Lenient by default**, strict mode opt-in. In lenient mode, anything not in the truthy set returns `False`.
- **Value set resolution** is two-phase: hardcoded defaults → config file → function arguments. `truthy` replaces, `extend_truthy` extends (ruff's select/extend-select pattern).
- **Three-state parameters** (`strict`, `warn`): `None` defers to config, `True`/`False` override.
- **Config caching**: loaded once on first use via double-checked locking. `_reset_config()` clears cache for tests.
- **Return type is always `bool`** — no `None` returns.

## Code Style

- Google-style docstrings (enforced by ruff)
- Line length: 88 chars
- All ruff rules enabled with pragmatic ignores (see `pyproject.toml` for details)
- Tests are exempt from docstring and type annotation rules

## Testing Notes

- Config tests need `tmp_path` + `monkeypatch.chdir()` for isolation.
- Every test should start with clean config state — use `_reset_config()` in fixtures.
- `to_bool` tests should not touch `os.environ`; `envbool` tests use `monkeypatch.setenv`/`delenv`.
