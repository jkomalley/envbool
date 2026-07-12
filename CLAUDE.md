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

- `_defaults.py` — Built-in truthy/falsy sets, shared set-resolution helpers (`_normalize_set`, `_apply_replace_or_extend`), and the process-level `Defaults` dataclass with `set_defaults()` / `get_defaults()` / `reset_defaults()`. A leaf module: no imports from elsewhere in envbool.
- `_core.py` — Pure string coercion logic (`to_bool`, `_resolve`). No `os.environ` dependency.
- `_env.py` — `envbool()` function: reads env vars, delegates to `_core.py`.
- `exceptions.py` — `EnvBoolError` base, `InvalidBoolValueError(EnvBoolError, ValueError)`, `MissingEnvVarError(EnvBoolError, KeyError)`.
- `_cli.py` — CLI entry point using `argparse`.
- `__main__.py` — `python -m envbool` alias for the CLI.
- `__init__.py` — Public API re-exports.

Key design patterns:
- **Lenient by default**, strict mode opt-in. In lenient mode, anything not in the truthy set returns `False`.
- **Value set resolution** is two-phase: hardcoded defaults → `set_defaults()` → function arguments. `truthy` replaces, `extend_truthy` extends (ruff's select/extend-select pattern).
- **Three-state parameters** (`strict`, `warn`): `None` defers to `set_defaults()`, `True`/`False` override.
- **Defaults caching**: a pre-populated in-memory `Defaults`; `set_defaults()`/`reset_defaults()` write under a lock. No disk I/O anywhere in the library.
- **Return type is always `bool`** — no `None` returns.

## Workflow

- Every feature, fix, or other change gets its own branch and pull request — no direct commits to main.
- Commits must be atomic: one logical change per commit, no bundling independent changes together.
- When there is any ambiguity in requirements or approach, ask questions before writing code.
- Follow DRY (Don't Repeat Yourself) — extract shared logic rather than duplicating it.

## Code Style

- Google-style docstrings (enforced by ruff)
- Line length: 88 chars
- All ruff rules enabled with pragmatic ignores (see `pyproject.toml` for details)
- Tests are exempt from docstring and type annotation rules
- Lean towards over-commenting: explain *why* code does something, not just *what* it does. Avoid redundant or obvious comments (e.g. `# increment i` above `i += 1`).

## Testing Notes

- Maintain 100% test coverage at all times — every new code path needs a test.
- Every test should end with clean defaults state — the autouse `reset_defaults()` fixture in conftest.py handles this.
- `to_bool` tests should not touch `os.environ`; `envbool` tests use `monkeypatch.setenv`/`delenv`.
