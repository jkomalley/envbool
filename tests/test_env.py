"""Tests for _env.py: envbool() function."""

import logging

import pytest

from envbool._config import _reset_config
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY
from envbool._env import envbool
from envbool.exceptions import InvalidBoolValueError


@pytest.fixture(autouse=True)
def reset_config():
    _reset_config()
    yield
    _reset_config()


# ---------------------------------------------------------------------------
# Unset / empty
# ---------------------------------------------------------------------------


class TestEnvBoolUnset:
    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert envbool("TEST_VAR") is False

    def test_unset_returns_custom_default(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert envbool("TEST_VAR", default=True) is True

    def test_empty_string_returns_false(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "")
        assert envbool("TEST_VAR") is False

    def test_whitespace_only_returns_false(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "   ")
        assert envbool("TEST_VAR") is False

    def test_whitespace_only_returns_custom_default(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "   ")
        assert envbool("TEST_VAR", default=True) is True


# ---------------------------------------------------------------------------
# Default truthy / falsy values
# ---------------------------------------------------------------------------


class TestEnvBoolTruthy:
    @pytest.mark.parametrize("value", sorted(DEFAULT_TRUTHY))
    def test_default_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("TEST_VAR", value)
        assert envbool("TEST_VAR") is True

    def test_uppercase_truthy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "TRUE")
        assert envbool("TEST_VAR") is True

    def test_mixed_case_truthy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "True")
        assert envbool("TEST_VAR") is True

    def test_whitespace_padded_truthy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "  true  ")
        assert envbool("TEST_VAR") is True


class TestEnvBoolFalsy:
    @pytest.mark.parametrize("value", sorted(DEFAULT_FALSY))
    def test_default_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("TEST_VAR", value)
        assert envbool("TEST_VAR") is False

    def test_uppercase_falsy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "FALSE")
        assert envbool("TEST_VAR") is False

    def test_unrecognized_lenient(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "maybe")
        assert envbool("TEST_VAR") is False


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


class TestEnvBoolStrict:
    def test_unrecognized_raises_in_strict_mode(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with pytest.raises(InvalidBoolValueError):
            envbool("TEST_VAR", strict=True)

    def test_error_var_attribute_is_populated(self, monkeypatch):
        monkeypatch.setenv("MY_FLAG", "maybe")
        with pytest.raises(InvalidBoolValueError) as exc_info:
            envbool("MY_FLAG", strict=True)
        assert exc_info.value.var == "MY_FLAG"

    def test_error_value_attribute_is_normalized(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "  MAYBE  ")
        with pytest.raises(InvalidBoolValueError) as exc_info:
            envbool("TEST_VAR", strict=True)
        assert exc_info.value.value == "maybe"

    def test_error_message_contains_var_name(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "oops")
        with pytest.raises(InvalidBoolValueError) as exc_info:
            envbool("DEBUG", strict=True)
        assert "DEBUG" in str(exc_info.value)

    def test_strict_none_defaults_to_lenient(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "maybe")
        assert envbool("TEST_VAR", strict=None) is False

    def test_strict_none_defers_to_config(self, monkeypatch, tmp_path):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        with pytest.raises(InvalidBoolValueError):
            envbool("TEST_VAR", strict=None)

    def test_strict_false_overrides_config(self, monkeypatch, tmp_path):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        assert envbool("TEST_VAR", strict=False) is False

    def test_recognized_truthy_does_not_raise_in_strict(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "true")
        assert envbool("TEST_VAR", strict=True) is True

    def test_recognized_falsy_does_not_raise_in_strict(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "false")
        assert envbool("TEST_VAR", strict=True) is False


# ---------------------------------------------------------------------------
# Warn mode
# ---------------------------------------------------------------------------


class TestEnvBoolWarn:
    def test_warn_true_logs_for_unrecognized(self, monkeypatch, caplog):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool("TEST_VAR", warn=True)
        assert any("maybe" in r.message for r in caplog.records)

    def test_warn_false_suppresses_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool("TEST_VAR", warn=False)
        assert not any("maybe" in r.message for r in caplog.records)

    def test_warn_none_defers_to_config(self, monkeypatch, tmp_path, caplog):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        monkeypatch.chdir(tmp_path)
        _reset_config()
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool("TEST_VAR", warn=None)
        assert any("maybe" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Custom value sets
# ---------------------------------------------------------------------------


class TestEnvBoolCustomSets:
    def test_extend_truthy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "enabled")
        assert envbool("TEST_VAR", extend_truthy={"enabled"}) is True

    def test_truthy_replaces_defaults(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "true")
        # "true" is no longer truthy after replacement
        assert envbool("TEST_VAR", truthy={"1"}) is False

    def test_extend_falsy(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "disabled")
        assert envbool("TEST_VAR", extend_falsy={"disabled"}) is False

    def test_custom_truthy_accepts_list(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "si")
        assert envbool("TEST_VAR", truthy=["si", "oui"]) is True

    def test_custom_truthy_accepts_tuple(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "si")
        assert envbool("TEST_VAR", truthy=("si", "oui")) is True
