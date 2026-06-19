"""End-to-end smoke tests that run the CLI in a real subprocess.

The in-process tests in test_cli.py call main()/_build_parser() directly, which
is fast but cannot catch packaging, entry-point, exit-code, or stdin/TTY
regressions. These invoke `python -m envbool` as a child process so the whole
path -- module discovery, argument parsing, real exit codes, real piped stdin --
is exercised exactly as a shell would see it.

These are additive smoke tests; the 100% coverage requirement is still measured
on the in-process suite (subprocess execution is not tracked by coverage).
"""

import os
import subprocess
import sys

from envbool import __main__  # noqa: F401 -- imported so coverage sees the module


def run(*args, env_overrides=None, stdin=None):
    """Run `python -m envbool ARGS` in a child process; return the CompletedProcess.

    ENVBOOL_NO_CONFIG=1 keeps the run hermetic -- no config file is discovered by
    walking up from the test's working directory.
    """
    env = {**os.environ, "ENVBOOL_NO_CONFIG": "1"}
    env.pop("TEST_VAR", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(  # noqa: S603 -- fixed, trusted argv (no shell, no user input)
        [sys.executable, "-m", "envbool", *args],
        capture_output=True,
        text=True,
        env=env,
        input=stdin,
        check=False,
    )


def test_module_runs_as_python_m():
    # --help is the one path with a stdin-independent, deterministic outcome, so it
    # cleanly proves `python -m envbool` resolves to the CLI entry point at all.
    result = run("--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_truthy_env_var_exits_0():
    result = run("TEST_VAR", env_overrides={"TEST_VAR": "true"})
    assert result.returncode == 0


def test_falsy_env_var_exits_1():
    result = run("TEST_VAR", env_overrides={"TEST_VAR": "false"})
    assert result.returncode == 1


def test_unset_env_var_exits_1():
    result = run("TEST_VAR")
    assert result.returncode == 1


def test_strict_unrecognized_exits_2_with_error():
    result = run("--value", "maybe", "--strict")
    assert result.returncode == 2
    assert "error" in result.stderr.lower()


def test_value_print_outputs_true():
    result = run("--value", "yes", "--print")
    assert result.returncode == 0
    assert result.stdout.strip() == "true"


def test_piped_stdin_truthy_exits_0():
    result = run(stdin="true\n")
    assert result.returncode == 0


def test_piped_stdin_falsy_exits_1():
    result = run(stdin="false\n")
    assert result.returncode == 1
