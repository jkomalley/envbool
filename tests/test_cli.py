"""Tests for _cli.py: main() and _build_parser()."""

import sys
from io import StringIO

import pytest

from envbool._cli import main
from envbool._config import _reset_config


def run_cli(*args, monkeypatch, stdin_text=None, is_tty=True):
    """Invoke main() with controlled argv/stdin. Returns (stdout, stderr, exit_code)."""
    monkeypatch.setattr(sys, "argv", ["envbool", *args])
    if stdin_text is not None:
        fake_stdin = StringIO(stdin_text)
        fake_stdin.isatty = lambda: False
        monkeypatch.setattr(sys, "stdin", fake_stdin)
    else:
        fake_stdin = StringIO("")
        fake_stdin.isatty = lambda: is_tty
        monkeypatch.setattr(sys, "stdin", fake_stdin)

    with pytest.raises(SystemExit) as exc_info:
        main()
    return exc_info.value.code


# ---------------------------------------------------------------------------
# Exit codes via env var
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    def test_truthy_env_var_exits_0(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "true")
        code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 0

    def test_falsy_env_var_exits_1(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "false")
        code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 1

    def test_unset_env_var_exits_1(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 1

    def test_default_flag_with_unset_exits_0(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        code = run_cli("TEST_VAR", "--default", monkeypatch=monkeypatch)
        assert code == 0

    def test_strict_violation_exits_2(self, monkeypatch, capsys):
        monkeypatch.setenv("TEST_VAR", "maybe")
        code = run_cli("TEST_VAR", "--strict", monkeypatch=monkeypatch)
        assert code == 2
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


# ---------------------------------------------------------------------------
# --warn flag
# ---------------------------------------------------------------------------


class TestCLIWarnFlag:
    def test_warn_flag_logs_warning_on_unrecognized_value(self, monkeypatch, caplog):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level("WARNING"):
            code = run_cli("TEST_VAR", "--warn", monkeypatch=monkeypatch)
        assert code == 1
        assert "maybe" in caplog.text

    def test_no_warn_flag_logs_nothing(self, monkeypatch, caplog):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level("WARNING"):
            code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 1
        assert caplog.text == ""


# ---------------------------------------------------------------------------
# --value flag
# ---------------------------------------------------------------------------


class TestCLIValueFlag:
    def test_value_truthy_exits_0(self, monkeypatch):
        code = run_cli("--value", "yes", monkeypatch=monkeypatch)
        assert code == 0

    def test_value_falsy_exits_1(self, monkeypatch):
        code = run_cli("--value", "no", monkeypatch=monkeypatch)
        assert code == 1

    def test_value_unrecognized_lenient_exits_1(self, monkeypatch):
        code = run_cli("--value", "maybe", monkeypatch=monkeypatch)
        assert code == 1

    def test_value_unrecognized_strict_exits_2(self, monkeypatch):
        code = run_cli("--value", "maybe", "--strict", monkeypatch=monkeypatch)
        assert code == 2

    def test_value_and_var_name_mutual_exclusion(self, monkeypatch, capsys):
        monkeypatch.setenv("TEST_VAR", "true")
        code = run_cli("TEST_VAR", "--value", "yes", monkeypatch=monkeypatch)
        assert code == 2
        captured = capsys.readouterr()
        assert "mutually exclusive" in captured.err

    def test_value_case_insensitive(self, monkeypatch):
        code = run_cli("--value", "TRUE", monkeypatch=monkeypatch)
        assert code == 0

    def test_value_whitespace_stripped(self, monkeypatch):
        code = run_cli("--value", "  true  ", monkeypatch=monkeypatch)
        assert code == 0


# ---------------------------------------------------------------------------
# --print flag
# ---------------------------------------------------------------------------


class TestCLIPrintFlag:
    def test_print_truthy_outputs_true(self, monkeypatch, capsys):
        code = run_cli("--value", "yes", "--print", monkeypatch=monkeypatch)
        captured = capsys.readouterr()
        assert captured.out.strip() == "true"
        assert code == 0

    def test_print_falsy_outputs_false(self, monkeypatch, capsys):
        run_cli("--value", "no", "--print", monkeypatch=monkeypatch)
        captured = capsys.readouterr()
        assert captured.out.strip() == "false"

    def test_print_env_var_truthy(self, monkeypatch, capsys):
        monkeypatch.setenv("TEST_VAR", "1")
        run_cli("TEST_VAR", "--print", monkeypatch=monkeypatch)
        captured = capsys.readouterr()
        assert captured.out.strip() == "true"

    def test_print_env_var_falsy(self, monkeypatch, capsys):
        monkeypatch.setenv("TEST_VAR", "0")
        run_cli("TEST_VAR", "--print", monkeypatch=monkeypatch)
        captured = capsys.readouterr()
        assert captured.out.strip() == "false"


# ---------------------------------------------------------------------------
# Stdin piping
# ---------------------------------------------------------------------------


class TestCLIStdin:
    def test_stdin_truthy_exits_0(self, monkeypatch):
        code = run_cli(monkeypatch=monkeypatch, stdin_text="true\n")
        assert code == 0

    def test_stdin_falsy_exits_1(self, monkeypatch):
        code = run_cli(monkeypatch=monkeypatch, stdin_text="false\n")
        assert code == 1

    def test_stdin_whitespace_stripped(self, monkeypatch):
        code = run_cli(monkeypatch=monkeypatch, stdin_text="  yes  \n")
        assert code == 0

    def test_stdin_multiline_exits_2(self, monkeypatch, capsys):
        code = run_cli(monkeypatch=monkeypatch, stdin_text="yes\nno\n")
        assert code == 2
        captured = capsys.readouterr()
        assert "single value" in captured.err

    def test_stdin_unrecognized_lenient_exits_1(self, monkeypatch):
        code = run_cli(monkeypatch=monkeypatch, stdin_text="maybe\n")
        assert code == 1

    def test_stdin_unrecognized_strict_exits_2(self, monkeypatch):
        code = run_cli("--strict", monkeypatch=monkeypatch, stdin_text="maybe\n")
        assert code == 2


# ---------------------------------------------------------------------------
# No input (TTY, no args)
# ---------------------------------------------------------------------------


class TestCLINoInput:
    def test_no_args_tty_exits_2(self, monkeypatch, capsys):
        code = run_cli(monkeypatch=monkeypatch, is_tty=True)
        assert code == 2
        captured = capsys.readouterr()
        # usage goes to stderr
        assert "usage" in captured.err.lower()


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------


class TestCLIConfigIntegration:
    def test_config_strict_propagates(self, monkeypatch, tmp_path):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 2

    def test_cli_strict_flag_overrides_config_false(self, monkeypatch, tmp_path):
        (tmp_path / "envbool.toml").write_text("strict = false\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        code = run_cli("TEST_VAR", "--strict", monkeypatch=monkeypatch)
        assert code == 2

    def test_config_warn_propagates(self, monkeypatch, tmp_path, caplog):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level("WARNING"):
            run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert "maybe" in caplog.text

    def test_config_extend_truthy_propagates(self, monkeypatch, tmp_path):
        (tmp_path / "envbool.toml").write_text('extend_truthy = ["enabled"]\n')
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "enabled")
        code = run_cli("TEST_VAR", monkeypatch=monkeypatch)
        assert code == 0


# ---------------------------------------------------------------------------
# Custom truthy/falsy value sets (--truthy/--falsy/--extend-truthy/--extend-falsy)
# ---------------------------------------------------------------------------


class TestCLIValueSets:
    def test_truthy_replaces_default_set(self, monkeypatch):
        # "true" is a default truthy value but is excluded once --truthy replaces
        # the set entirely, so it should now be treated as unrecognized (falsy).
        monkeypatch.setenv("TEST_VAR", "true")
        code = run_cli("TEST_VAR", "--truthy", "yes", monkeypatch=monkeypatch)
        assert code == 1

    def test_truthy_replace_recognizes_custom_value(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "yes")
        code = run_cli("TEST_VAR", "--truthy", "yes", monkeypatch=monkeypatch)
        assert code == 0

    def test_falsy_replaces_default_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "off")
        code = run_cli("TEST_VAR", "--falsy", "nope", monkeypatch=monkeypatch)
        # "off" is no longer in the (replaced) falsy set and isn't truthy either,
        # so lenient mode falls back to False -> exit 1.
        assert code == 1

    def test_extend_truthy_adds_to_defaults(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "enabled")
        code = run_cli(
            "TEST_VAR", "--extend-truthy", "enabled", monkeypatch=monkeypatch
        )
        assert code == 0

    def test_extend_truthy_keeps_defaults(self, monkeypatch):
        # Default truthy values still work alongside the extension.
        monkeypatch.setenv("TEST_VAR", "true")
        code = run_cli(
            "TEST_VAR", "--extend-truthy", "enabled", monkeypatch=monkeypatch
        )
        assert code == 0

    def test_extend_falsy_adds_to_defaults(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "nope")
        code = run_cli("TEST_VAR", "--extend-falsy", "nope", monkeypatch=monkeypatch)
        assert code == 1

    def test_repeated_extend_truthy_accumulates(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "on2")
        code = run_cli(
            "TEST_VAR",
            "--extend-truthy",
            "on1",
            "--extend-truthy",
            "on2",
            monkeypatch=monkeypatch,
        )
        assert code == 0

    def test_combined_truthy_and_extend_falsy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "nope")
        code = run_cli(
            "TEST_VAR",
            "--truthy",
            "yes",
            "--extend-falsy",
            "nope",
            monkeypatch=monkeypatch,
        )
        assert code == 1


# ---------------------------------------------------------------------------
# --show-config flag
# ---------------------------------------------------------------------------


class TestCLIShowConfig:
    def test_no_config_file_prints_defaults(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "1")
        _reset_config()
        code = run_cli("--show-config", monkeypatch=monkeypatch)
        assert code == 0
        out = capsys.readouterr().out
        assert "config file: none" in out
        assert "strict:      false" in out
        assert "warn:        false" in out

    def test_config_file_path_and_values_printed(self, monkeypatch, tmp_path, capsys):
        config_file = tmp_path / "envbool.toml"
        config_file.write_text('strict = true\nwarn = true\ntruthy = ["yep"]\n')
        monkeypatch.chdir(tmp_path)
        _reset_config()
        code = run_cli("--show-config", monkeypatch=monkeypatch)
        assert code == 0
        out = capsys.readouterr().out
        assert str(config_file) in out
        assert "strict:      true" in out
        assert "warn:        true" in out
        assert "truthy:      yep" in out

    def test_cli_strict_flag_overrides_printed_strict(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "1")
        _reset_config()
        code = run_cli("--show-config", "--strict", monkeypatch=monkeypatch)
        assert code == 0
        out = capsys.readouterr().out
        assert "strict:      true" in out

    def test_cli_warn_flag_overrides_printed_warn(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "1")
        _reset_config()
        code = run_cli("--show-config", "--warn", monkeypatch=monkeypatch)
        assert code == 0
        out = capsys.readouterr().out
        assert "warn:        true" in out

    def test_cli_extend_truthy_reflected_in_printed_truthy(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "1")
        _reset_config()
        code = run_cli(
            "--show-config", "--extend-truthy", "maybe", monkeypatch=monkeypatch
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "maybe" in out

    def test_show_config_with_var_name_exits_2(self, monkeypatch, capsys):
        monkeypatch.setenv("TEST_VAR", "true")
        code = run_cli("--show-config", "TEST_VAR", monkeypatch=monkeypatch)
        assert code == 2
        assert "mutually exclusive" in capsys.readouterr().err

    def test_show_config_with_value_exits_2(self, monkeypatch, capsys):
        code = run_cli("--show-config", "--value", "yes", monkeypatch=monkeypatch)
        assert code == 2
        assert "mutually exclusive" in capsys.readouterr().err

    def test_show_config_with_print_exits_2(self, monkeypatch, capsys):
        code = run_cli("--show-config", "--print", monkeypatch=monkeypatch)
        assert code == 2
        assert "mutually exclusive" in capsys.readouterr().err

    def test_show_config_with_default_exits_2(self, monkeypatch, capsys):
        code = run_cli("--show-config", "--default", monkeypatch=monkeypatch)
        assert code == 2
        assert "mutually exclusive" in capsys.readouterr().err
