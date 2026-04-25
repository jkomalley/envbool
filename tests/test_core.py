"""Tests for core.py: DEFAULT_TRUTHY, DEFAULT_FALSY, _resolve, and to_bool."""

import logging

import pytest

from envbool._core import DEFAULT_FALSY, DEFAULT_TRUTHY, _resolve, to_bool
from envbool.exceptions import EnvBoolError, InvalidBoolValueError


class TestDefaults:
    def test_default_truthy_is_frozenset(self):
        assert isinstance(DEFAULT_TRUTHY, frozenset)

    def test_default_falsy_is_frozenset(self):
        assert isinstance(DEFAULT_FALSY, frozenset)

    def test_default_truthy_members(self):
        assert frozenset({"true", "1", "yes", "on"}) == DEFAULT_TRUTHY

    def test_default_falsy_members(self):
        assert frozenset({"false", "0", "no", "off"}) == DEFAULT_FALSY

    def test_defaults_are_disjoint(self):
        assert DEFAULT_TRUTHY.isdisjoint(DEFAULT_FALSY)


class TestResolveDefaults:
    def test_no_args_returns_defaults(self):
        t, f = _resolve()
        assert t == DEFAULT_TRUTHY
        assert f == DEFAULT_FALSY

    def test_config_truthy_used_when_no_arg_override(self):
        custom = frozenset({"si", "oui"})
        t, f = _resolve(config_truthy=custom)
        assert t == custom
        assert f == DEFAULT_FALSY

    def test_config_falsy_used_when_no_arg_override(self):
        custom = frozenset({"nope", "nein"})
        t, f = _resolve(config_falsy=custom)
        assert t == DEFAULT_TRUTHY
        assert f == custom

    def test_return_type_is_frozenset_pair(self):
        result = _resolve()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], frozenset)
        assert isinstance(result[1], frozenset)


class TestResolveTruthy:
    def test_truthy_replaces_config_truthy(self):
        t, _ = _resolve(truthy=["si"])
        assert t == frozenset({"si"})

    def test_truthy_replaces_default_truthy(self):
        t, _ = _resolve(truthy=["enabled"])
        assert "true" not in t
        assert "enabled" in t

    def test_truthy_empty_set_allowed(self):
        t, _ = _resolve(truthy=set())
        assert t == frozenset()

    def test_extend_truthy_adds_to_config_truthy(self):
        t, _ = _resolve(extend_truthy=["enabled"])
        assert "enabled" in t
        assert DEFAULT_TRUTHY.issubset(t)

    def test_extend_truthy_adds_to_custom_config_truthy(self):
        config = frozenset({"si"})
        t, _ = _resolve(config_truthy=config, extend_truthy=["ja"])
        assert t == frozenset({"si", "ja"})

    def test_truthy_takes_priority_over_extend_truthy(self):
        t, _ = _resolve(truthy=["only"], extend_truthy=["ignored"])
        assert t == frozenset({"only"})

    def test_truthy_accepts_list(self):
        t, _ = _resolve(truthy=["a", "b"])
        assert t == frozenset({"a", "b"})

    def test_truthy_accepts_tuple(self):
        t, _ = _resolve(truthy=("a", "b"))
        assert t == frozenset({"a", "b"})

    def test_truthy_accepts_set(self):
        t, _ = _resolve(truthy={"a", "b"})
        assert t == frozenset({"a", "b"})

    def test_extend_truthy_accepts_list(self):
        t, _ = _resolve(extend_truthy=["extra"])
        assert "extra" in t

    def test_extend_truthy_accepts_tuple(self):
        t, _ = _resolve(extend_truthy=("extra",))
        assert "extra" in t

    def test_extend_truthy_does_not_affect_falsy(self):
        _, f = _resolve(extend_truthy=["extra"])
        assert f == DEFAULT_FALSY


class TestResolveFalsy:
    def test_falsy_replaces_config_falsy(self):
        _, f = _resolve(falsy=["nope"])
        assert f == frozenset({"nope"})

    def test_falsy_replaces_default_falsy(self):
        _, f = _resolve(falsy=["disabled"])
        assert "false" not in f
        assert "disabled" in f

    def test_falsy_empty_set_allowed(self):
        _, f = _resolve(falsy=set())
        assert f == frozenset()

    def test_extend_falsy_adds_to_config_falsy(self):
        _, f = _resolve(extend_falsy=["disabled"])
        assert "disabled" in f
        assert DEFAULT_FALSY.issubset(f)

    def test_extend_falsy_adds_to_custom_config_falsy(self):
        config = frozenset({"nein"})
        _, f = _resolve(config_falsy=config, extend_falsy=["nope"])
        assert f == frozenset({"nein", "nope"})

    def test_falsy_takes_priority_over_extend_falsy(self):
        _, f = _resolve(falsy=["only"], extend_falsy=["ignored"])
        assert f == frozenset({"only"})

    def test_falsy_accepts_list(self):
        _, f = _resolve(falsy=["a", "b"])
        assert f == frozenset({"a", "b"})

    def test_falsy_accepts_tuple(self):
        _, f = _resolve(falsy=("a", "b"))
        assert f == frozenset({"a", "b"})

    def test_falsy_accepts_set(self):
        _, f = _resolve(falsy={"a", "b"})
        assert f == frozenset({"a", "b"})

    def test_extend_falsy_does_not_affect_truthy(self):
        t, _ = _resolve(extend_falsy=["extra"])
        assert t == DEFAULT_TRUTHY


class TestResolveBothSides:
    def test_truthy_and_falsy_independently_replaceable(self):
        t, f = _resolve(truthy=["yes"], falsy=["no"])
        assert t == frozenset({"yes"})
        assert f == frozenset({"no"})

    def test_extend_both_sides_independently(self):
        t, f = _resolve(extend_truthy=["enabled"], extend_falsy=["disabled"])
        assert "enabled" in t
        assert DEFAULT_TRUTHY.issubset(t)
        assert "disabled" in f
        assert DEFAULT_FALSY.issubset(f)

    def test_truthy_replace_with_extend_falsy(self):
        t, f = _resolve(truthy=["si"], extend_falsy=["disabled"])
        assert t == frozenset({"si"})
        assert "disabled" in f
        assert DEFAULT_FALSY.issubset(f)


class TestToBoolDefaults:
    def test_true_values(self):
        for v in ("true", "1", "yes", "on"):
            assert to_bool(v) is True

    def test_false_values(self):
        for v in ("false", "0", "no", "off"):
            assert to_bool(v) is False

    def test_case_insensitive_upper(self):
        assert to_bool("TRUE") is True
        assert to_bool("YES") is True

    def test_case_insensitive_mixed(self):
        assert to_bool("True") is True

    def test_leading_trailing_whitespace(self):
        assert to_bool("  true  ") is True
        assert to_bool(" false ") is False

    def test_empty_string_returns_default_false(self):
        assert to_bool("") is False

    def test_empty_string_returns_default_true(self):
        assert to_bool("", default=True) is True

    def test_whitespace_only_returns_default(self):
        assert to_bool("   ") is False

    def test_unrecognized_lenient_returns_false(self):
        assert to_bool("maybe") is False

    def test_return_type_is_bool(self):
        assert type(to_bool("true")) is bool
        assert type(to_bool("false")) is bool
        assert type(to_bool("")) is bool


class TestToBoolStrict:
    def test_unrecognized_strict_raises(self):
        with pytest.raises(InvalidBoolValueError):
            to_bool("maybe", strict=True)

    def test_unrecognized_strict_none_is_lenient(self):
        assert to_bool("maybe", strict=None) is False

    def test_recognized_truthy_strict_does_not_raise(self):
        assert to_bool("true", strict=True) is True

    def test_recognized_falsy_strict_returns_false(self):
        assert to_bool("false", strict=True) is False

    def test_empty_strict_returns_default(self):
        assert to_bool("", strict=True) is False
        assert to_bool("", strict=True, default=True) is True

    def test_error_is_invalid_bool_value_error(self):
        with pytest.raises(InvalidBoolValueError):
            to_bool("nope", strict=True)

    def test_error_is_envbool_error(self):
        with pytest.raises(EnvBoolError):
            to_bool("nope", strict=True)

    def test_error_is_value_error(self):
        with pytest.raises(ValueError, match="nope"):
            to_bool("nope", strict=True)

    def test_error_attributes(self):
        with pytest.raises(InvalidBoolValueError) as exc_info:
            to_bool("maybe", strict=True)
        err = exc_info.value
        assert err.value == "maybe"
        assert err.truthy == DEFAULT_TRUTHY
        assert err.falsy == DEFAULT_FALSY
        assert err.var is None

    def test_error_message_contains_value(self):
        with pytest.raises(InvalidBoolValueError, match="maybe"):
            to_bool("maybe", strict=True)

    def test_error_normalizes_value(self):
        with pytest.raises(InvalidBoolValueError) as exc_info:
            to_bool("  MAYBE  ", strict=True)
        assert exc_info.value.value == "maybe"


class TestToBoolWarn:
    def test_warn_true_emits_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            to_bool("maybe", warn=True)
        assert caplog.records

    def test_warn_false_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            to_bool("maybe", warn=False)
        assert not caplog.records

    def test_warn_none_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            to_bool("maybe", warn=None)
        assert not caplog.records

    def test_warn_not_emitted_for_recognized_value(self, caplog):
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            to_bool("true", warn=True)
        assert not caplog.records


class TestToBoolCustomSets:
    def test_truthy_replaces(self):
        assert to_bool("enabled", truthy=["enabled"]) is True
        assert to_bool("true", truthy=["enabled"]) is False

    def test_extend_truthy_adds(self):
        assert to_bool("enabled", extend_truthy=["enabled"]) is True
        assert to_bool("true", extend_truthy=["enabled"]) is True

    def test_falsy_replaces(self):
        assert to_bool("disabled", falsy=["disabled"], strict=True) is False

    def test_extend_falsy_adds(self):
        assert to_bool("disabled", extend_falsy=["disabled"], strict=True) is False
        assert to_bool("false", extend_falsy=["disabled"], strict=True) is False

    def test_truthy_takes_priority_over_extend_truthy(self):
        assert to_bool("only", truthy=["only"], extend_truthy=["ignored"]) is True
        assert to_bool("ignored", truthy=["only"], extend_truthy=["ignored"]) is False

    def test_empty_truthy_set(self):
        assert to_bool("true", truthy=set()) is False

    def test_empty_truthy_strict_raises(self):
        with pytest.raises(InvalidBoolValueError):
            to_bool("true", truthy=set(), strict=True)

    def test_error_attributes_reflect_custom_sets(self):
        custom_truthy = frozenset({"yes"})
        custom_falsy = frozenset({"no"})
        with pytest.raises(InvalidBoolValueError) as exc_info:
            to_bool("maybe", truthy=custom_truthy, falsy=custom_falsy, strict=True)
        err = exc_info.value
        assert err.truthy == custom_truthy
        assert err.falsy == custom_falsy


class TestToBoolOverlap:
    def test_overlap_truthy_wins(self):
        assert to_bool("true", truthy=["true"], falsy=["true"]) is True

    def test_overlap_emits_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            to_bool("true", truthy=["true"], falsy=["true"])
        assert caplog.records


class TestToBoolVar:
    def test_var_in_error_message(self):
        with pytest.raises(InvalidBoolValueError, match="MY_VAR"):
            to_bool("bad", strict=True, _var="MY_VAR")

    def test_var_attribute_set(self):
        with pytest.raises(InvalidBoolValueError) as exc_info:
            to_bool("bad", strict=True, _var="MY_VAR")
        assert exc_info.value.var == "MY_VAR"

    def test_var_none_no_var_in_message(self):
        with pytest.raises(InvalidBoolValueError) as exc_info:
            to_bool("bad", strict=True)
        assert "for " not in str(exc_info.value)


class TestResolveNormalization:
    def test_truthy_values_are_lowercased(self):
        # Normalized so they match the lowercased input that to_bool() produces.
        eff_truthy, _ = _resolve(truthy={"Enabled", "YES"})
        assert "enabled" in eff_truthy
        assert "yes" in eff_truthy
        assert "Enabled" not in eff_truthy

    def test_truthy_values_are_stripped(self):
        eff_truthy, _ = _resolve(truthy={"  enabled  "})
        assert "enabled" in eff_truthy

    def test_extend_truthy_values_are_normalized(self):
        eff_truthy, _ = _resolve(extend_truthy={"ENABLED"})
        assert "enabled" in eff_truthy
        assert "true" in eff_truthy  # default still present

    def test_falsy_values_are_normalized(self):
        _, eff_falsy = _resolve(falsy={"NOPE"})
        assert "nope" in eff_falsy
        assert "NOPE" not in eff_falsy

    def test_extend_falsy_values_are_normalized(self):
        _, eff_falsy = _resolve(extend_falsy={"  Nope  "})
        assert "nope" in eff_falsy
        assert "false" in eff_falsy  # default still present

    def test_to_bool_with_mixed_case_truthy_arg(self):
        assert to_bool("enabled", truthy={"Enabled"}) is True

    def test_to_bool_with_mixed_case_extend_truthy_arg(self):
        assert to_bool("enabled", extend_truthy={"ENABLED"}) is True
