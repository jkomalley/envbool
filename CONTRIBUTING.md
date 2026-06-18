# Contributing to envbool

Thanks for your interest in improving `envbool`. This guide covers everything
you need to get set up and land a change. For library *usage*, see the
[README](README.md).

## Ways to contribute

- **Report a bug** or **request a feature** by [opening an issue](https://github.com/jkomalley/envbool/issues).
- **Submit a pull request** for a fix or improvement.

For anything large or behavior-changing, please open an issue to discuss the
approach before investing time in a PR.

## Development setup

**Prerequisites:** Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jkomalley/envbool.git
cd envbool
uv sync                    # create the venv and install all dependencies
uv run pre-commit install  # enable the git hooks
```

That's it — `uv sync` installs the project and its dev tooling into a managed
virtual environment.

## Project layout

The package uses a `src/` layout. Each module has a single, focused
responsibility:

| Module | Responsibility |
| --- | --- |
| `_core.py` | Pure string-to-bool coercion (`to_bool`) and value-set resolution. No `os.environ` access. |
| `_env.py` | `envbool()` — reads the environment, then delegates to `_core`. |
| `_config.py` | Config-file discovery, TOML parsing, and the thread-safe config cache. |
| `_defaults.py` | The built-in `DEFAULT_TRUTHY` / `DEFAULT_FALSY` sets. |
| `_cli.py` | The `envbool` command-line entry point. |
| `exceptions.py` | The `EnvBoolError` exception hierarchy. |
| `__init__.py` | The public API surface (re-exports). |

Implementation modules are underscore-prefixed so the public surface can evolve
without breaking imports. Import from `envbool`, not from `envbool._core` and
friends.

## Running checks

The repo uses [`just`](https://github.com/casey/just) as a task runner. Run
everything before pushing:

```bash
just            # format + lint + typecheck + test
```

Or run individual tasks:

```bash
just format     # ruff format
just lint       # ruff check
just typecheck  # ty check
just test       # pytest
just cov        # pytest with coverage
```

Each task maps to a plain `uv run …` command, so you can run them directly if
you'd rather not install `just`.

## Coding standards

- **Style & linting:** [`ruff`](https://docs.astral.sh/ruff/) with nearly all
  rules enabled (see `pyproject.toml` for the pragmatic exceptions). Run
  `just format` and `just lint` before committing.
- **Type checking:** the codebase is fully typed; `just typecheck` must pass.
- **Docstrings:** Google-style, on every public function and class.
- **Comments:** explain *why*, not *what*. Lean toward documenting non-obvious
  decisions; skip comments that merely restate the code.
- **Line length:** 88 characters.

### Testing

- **100% coverage is required.** Every new code path needs a test; check with
  `just cov`.
- Config tests must isolate the filesystem with `tmp_path` and
  `monkeypatch.chdir()`.
- `to_bool()` tests must not touch `os.environ`; use `monkeypatch.setenv` /
  `delenv` in `envbool()` tests instead.
- Every test starts from a clean config cache — the autouse
  `_reset_envbool_config` fixture in `conftest.py` handles this for you.

## Pull requests

- Branch off `main`; one logical change per PR.
- Keep commits atomic — a single coherent change each, not a bundle of unrelated
  edits.
- Include tests for any new or changed behavior.
- Make sure `just` passes cleanly before you open the PR.

CI runs the full check suite against Python 3.11–3.14 on every pull request.

## Releasing

Releases are published to PyPI automatically: the CD workflow fires when CI
passes on `main` and publishes whenever `pyproject.toml`'s version isn't already
on PyPI. So a release is just a version bump merged to `main`.

Choose the bump from the changes since the **last release tag**, not just your
latest work:

```bash
git log "$(git describe --tags --abbrev=0)"..HEAD --oneline
```

Map the conventional-commit types in that range to a [semver](https://semver.org/)
bump and apply it with `uv`:

| Changes since last release | Bump | Command |
| --- | --- | --- |
| Any `feat:` | minor | `uv version --bump minor` |
| Only `fix:` / `docs:` / `chore:` | patch | `uv version --bump patch` |
| A breaking change (`feat!:`, `BREAKING CHANGE`) | major¹ | `uv version --bump major` |

¹ While the project is pre-1.0, breaking changes are released as a **minor**
bump per semver's 0.x convention.

Open the bump as its own PR. The `version-guard` CI job enforces this: it fails
any release PR whose bump is too small for the commits since the last release
(for example, shipping a `feat:` in a patch). Features merged to `main` without
a release accumulate, so the bump must account for all of them — not just the
most recent change.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
