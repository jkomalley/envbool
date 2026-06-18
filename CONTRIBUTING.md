# Contributing to envbool

This document covers development setup and guidelines for contributors. For
library usage (including advanced topics like testing, exceptions, and
logging), see [README.md](README.md).

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
