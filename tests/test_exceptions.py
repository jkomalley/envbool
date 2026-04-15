"""Tests for the envbool exception hierarchy.

Validates class structure, inheritance chains, MRO ordering, and annotated
attributes. Integration-level tests (verifying exceptions are raised with
correct attributes) belong in the modules that raise them (core, config).
"""

from pathlib import Path

import pytest

from envbool.exceptions import ConfigError, EnvBoolError, InvalidBoolValueError


class TestEnvBoolError:
    """Base exception: inherits from Exception, carries a message."""

    def test_is_exception(self):
        assert issubclass(EnvBoolError, Exception)

    def test_instantiate_with_message(self):
        err = EnvBoolError("something went wrong")
        assert str(err) == "something went wrong"

    def test_instantiate_no_args(self):
        err = EnvBoolError()
        assert str(err) == ""

    def test_raises_as_exception(self):
        with pytest.raises(EnvBoolError, match="boom"):
            raise EnvBoolError("boom")


class TestInvalidBoolValueError:
    """Dual-inheritance: EnvBoolError + ValueError.

    Must be caught as either parent so existing ``except ValueError``
    handlers keep working after adoption.
    """

    # --- inheritance ---

    def test_is_envbool_error(self):
        assert issubclass(InvalidBoolValueError, EnvBoolError)

    def test_is_value_error(self):
        assert issubclass(InvalidBoolValueError, ValueError)

    def test_not_config_error(self):
        assert not issubclass(InvalidBoolValueError, ConfigError)

    def test_mro_order(self):
        """EnvBoolError should appear before ValueError in the MRO."""
        mro = InvalidBoolValueError.__mro__
        envbool_idx = mro.index(EnvBoolError)
        value_idx = mro.index(ValueError)
        assert envbool_idx < value_idx

    # --- raises as parent types ---

    def test_raises_as_value_error(self):
        with pytest.raises(ValueError, match="bad value"):
            raise InvalidBoolValueError("bad value")

    def test_raises_as_envbool_error(self):
        with pytest.raises(EnvBoolError):
            raise InvalidBoolValueError("bad value")

    # --- message ---

    def test_instantiate_with_message(self):
        err = InvalidBoolValueError("not a bool")
        assert str(err) == "not a bool"

    # --- annotated attributes ---

    def test_var_attribute(self):
        err = InvalidBoolValueError("bad")
        err.var = "MY_VAR"
        assert err.var == "MY_VAR"

    def test_var_attribute_none(self):
        """var is None when raised from to_bool() (no env var context)."""
        err = InvalidBoolValueError("bad")
        err.var = None
        assert err.var is None

    def test_value_attribute(self):
        err = InvalidBoolValueError("bad")
        err.value = "maybe"
        assert err.value == "maybe"

    def test_truthy_attribute(self):
        err = InvalidBoolValueError("bad")
        err.truthy = frozenset({"true", "1", "yes"})
        assert err.truthy == frozenset({"true", "1", "yes"})

    def test_truthy_attribute_empty(self):
        err = InvalidBoolValueError("bad")
        err.truthy = frozenset()
        assert err.truthy == frozenset()

    def test_falsy_attribute(self):
        err = InvalidBoolValueError("bad")
        err.falsy = frozenset({"false", "0", "no"})
        assert err.falsy == frozenset({"false", "0", "no"})

    def test_falsy_attribute_empty(self):
        err = InvalidBoolValueError("bad")
        err.falsy = frozenset()
        assert err.falsy == frozenset()


class TestConfigError:
    """Raised for malformed config files. Not a ValueError."""

    # --- inheritance ---

    def test_is_envbool_error(self):
        assert issubclass(ConfigError, EnvBoolError)

    def test_not_value_error(self):
        assert not issubclass(ConfigError, ValueError)

    def test_not_invalid_bool_value_error(self):
        assert not issubclass(ConfigError, InvalidBoolValueError)

    # --- raises as parent type ---

    def test_raises_as_envbool_error(self):
        with pytest.raises(EnvBoolError):
            raise ConfigError("bad config")

    # --- message ---

    def test_instantiate_with_message(self):
        err = ConfigError("invalid toml")
        assert str(err) == "invalid toml"

    # --- annotated attributes ---

    def test_path_attribute(self, tmp_path):
        p = tmp_path / "envbool.toml"
        err = ConfigError("bad config")
        err.path = p
        assert err.path == p

    def test_path_attribute_relative(self):
        err = ConfigError("bad config")
        err.path = Path("pyproject.toml")
        assert err.path == Path("pyproject.toml")
