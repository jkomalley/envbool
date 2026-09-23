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
uv run pre-commit install  # enable the pre-commit and pre-push git hooks
```

That's it — `uv sync` installs the project and its dev tooling into a managed
virtual environment. With [`just`](https://github.com/casey/just) installed,
`just install` runs both steps.

## Project layout

The package uses a `src/` layout. Each module has a single, focused
responsibility:

| Module | Responsibility |
| --- | --- |
| `_core.py` | Pure string-to-bool coercion (`to_bool`) and value-set resolution. No `os.environ` access. |
| `_env.py` | `envbool()` — reads the environment, then delegates to `_core`. |
| `_defaults.py` | The built-in `DEFAULT_TRUTHY` / `DEFAULT_FALSY` sets, shared set-resolution helpers, and the process-level defaults behind `set_defaults()` / `get_defaults()` / `reset_defaults()`. |
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
just check      # format + lint + typecheck + tests with coverage
```

Or run individual tasks:

```bash
just format     # ruff format
just lint       # ruff check
just typecheck  # ty check
just test       # pytest, fast (no coverage)
just test-cov   # pytest with the 100% coverage gate
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
  `just test-cov`.
- `to_bool()` tests must not touch `os.environ`; use `monkeypatch.setenv` /
  `delenv` in `envbool()` tests instead.
- Every test ends with clean process-level defaults — the autouse
  `_reset_envbool_defaults` fixture in `conftest.py` calls `reset_defaults()`
  for you.

## Pull requests

- Branch off `main`; one logical change per PR.
- Keep commits atomic — a single coherent change each, not a bundle of unrelated
  edits.
- Include tests for any new or changed behavior.
- Add a bullet under `## [Unreleased]` in `CHANGELOG.md` for any user-facing
  change, so the changelog is always release-ready (internal-only refactors,
  CI, and docs changes are exempt).
- Make sure `just check` passes cleanly before you open the PR.

CI runs the full check suite against Python 3.11–3.14 on every pull request.

## Releasing

Releases are published to PyPI automatically: the CD workflow fires when CI
passes on `main` and publishes whenever `pyproject.toml`'s version isn't already
on PyPI. So a release is just a version bump merged to `main`.

The GitHub release's notes come straight from `CHANGELOG.md`, so keep it
current as you go (see the changelog bullet under
[Pull requests](#pull-requests)). Cutting a release is then a
`chore: release vX.Y.Z` PR that, in one commit:

- bumps the version (below),
- renames `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and adds a fresh empty
  `## [Unreleased]` above it, and
- updates the compare links at the bottom of `CHANGELOG.md`.

If the bumped version has no `CHANGELOG.md` section, the release workflow fails
rather than shipping empty notes.

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
| A breaking change (`feat!:`, `BREAKING CHANGE`) | minor (pre-1.0)¹ | `uv version --bump minor` |

¹ While the project is pre-1.0, breaking changes are released as a **minor**
bump per semver's 0.x convention. Only once the project reaches 1.0 does a
breaking change call for `uv version --bump major`.

Open the bump as its own PR. The `version-guard` CI job enforces this: it fails
any release PR whose bump is too small for the commits since the last release
(for example, shipping a `feat:` in a patch). Features merged to `main` without
a release accumulate, so the bump must account for all of them — not just the
most recent change.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
