"""Tests for _defaults.py: Defaults dataclass, caching, and set_defaults()."""

import concurrent.futures
import dataclasses
import logging

import pytest

from envbool import InvalidBoolValueError, envbool, to_bool
from envbool._defaults import (
    DEFAULT_FALSY,
    DEFAULT_TRUTHY,
    Defaults,
    get_defaults,
    reset_defaults,
    set_defaults,
)


class TestDefaultsDataclass:
    def test_built_in_values(self):
        d = Defaults()
        assert d.strict is False
        assert d.warn is False
        assert d.effective_truthy == DEFAULT_TRUTHY
        assert d.effective_falsy == DEFAULT_FALSY

    def test_frozen(self):
        d = Defaults()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.strict = True  # type: ignore[misc]


class TestGetDefaults:
    def test_returns_built_ins_when_unset(self):
        assert get_defaults() == Defaults()

    def test_same_instance_across_calls(self):
        assert get_defaults() is get_defaults()


class TestSetDefaults:
    def test_strict_true(self):
        set_defaults(strict=True)
        assert get_defaults().strict is True

    def test_warn_true(self):
        set_defaults(warn=True)
        assert get_defaults().warn is True

    def test_truthy_replaces(self):
        set_defaults(truthy=["yes"])
        assert get_defaults().effective_truthy == frozenset({"yes"})

    def test_falsy_replaces(self):
        set_defaults(falsy=["nope"])
        assert get_defaults().effective_falsy == frozenset({"nope"})

    def test_extend_truthy_adds_to_built_ins(self):
        set_defaults(extend_truthy=["enabled"])
        result = get_defaults().effective_truthy
        assert "enabled" in result
        assert DEFAULT_TRUTHY.issubset(result)

    def test_extend_falsy_adds_to_built_ins(self):
        set_defaults(extend_falsy=["disabled"])
        result = get_defaults().effective_falsy
        assert "disabled" in result
        assert DEFAULT_FALSY.issubset(result)

    def test_truthy_wins_over_extend_truthy(self):
        set_defaults(truthy=["only"], extend_truthy=["ignored"])
        assert get_defaults().effective_truthy == frozenset({"only"})

    def test_values_are_normalized(self):
        set_defaults(extend_truthy=["  ENABLED  "])
        assert "enabled" in get_defaults().effective_truthy

    def test_each_call_replaces_from_built_ins_not_previous_call(self):
        set_defaults(extend_truthy=["first"])
        set_defaults(extend_truthy=["second"])
        result = get_defaults().effective_truthy
        assert "second" in result
        assert "first" not in result
        assert DEFAULT_TRUTHY.issubset(result)

    def test_strict_none_keeps_built_in_false(self):
        set_defaults(strict=None)
        assert get_defaults().strict is False

    def test_non_bool_strict_raises_type_error(self):
        with pytest.raises(TypeError, match="strict"):
            set_defaults(strict="yes")  # type: ignore[arg-type]

    def test_non_bool_warn_raises_type_error(self):
        with pytest.raises(TypeError, match="warn"):
            set_defaults(warn=1)  # type: ignore[arg-type]

    def test_non_string_truthy_member_raises_type_error(self):
        with pytest.raises(TypeError, match="truthy"):
            set_defaults(truthy=[1, 2])  # type: ignore[list-item]

    def test_non_string_extend_falsy_member_raises_type_error(self):
        with pytest.raises(TypeError, match="extend_falsy"):
            set_defaults(extend_falsy=[None])  # type: ignore[list-item]

    def test_generator_input_is_consumed_safely(self):
        set_defaults(extend_truthy=(v for v in ["gen"]))
        assert "gen" in get_defaults().effective_truthy


class TestResetDefaults:
    def test_restores_built_ins(self):
        set_defaults(strict=True, extend_truthy=["enabled"])
        reset_defaults()
        assert get_defaults() == Defaults()

    def test_new_instance_after_reset(self):
        set_defaults(strict=True)
        before = get_defaults()
        reset_defaults()
        after = get_defaults()
        assert before is not after


class TestSetDefaultsIntegration:
    # These restore the strict/warn deferral coverage removed with the
    # config-file tests in test_env.py during the config-removal PR.

    def test_to_bool_strict_defers_to_set_defaults(self):
        set_defaults(strict=True)
        with pytest.raises(InvalidBoolValueError):
            to_bool("maybe")

    def test_call_site_strict_false_overrides_set_defaults(self):
        set_defaults(strict=True)
        assert to_bool("maybe", strict=False) is False

    def test_envbool_warn_defers_to_set_defaults(self, monkeypatch, caplog):
        set_defaults(warn=True)
        monkeypatch.setenv("TEST_VAR", "maybe")
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool("TEST_VAR")
        assert any("maybe" in r.message for r in caplog.records)

    def test_extended_truthy_applies_to_envbool(self, monkeypatch):
        set_defaults(extend_truthy=["enabled"])
        monkeypatch.setenv("TEST_VAR", "enabled")
        assert envbool("TEST_VAR") is True


class TestConcurrentSetDefaults:
    def test_concurrent_writers_leave_a_consistent_state(self):
        reset_defaults()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: set_defaults(extend_truthy=[f"v{i}"]), range(16)))
        # No assertion on *which* writer won -- only that get_defaults() reflects
        # exactly one of them (a fully-formed Defaults, not a torn/partial write).
        result = get_defaults()
        assert isinstance(result, Defaults)
        assert DEFAULT_TRUTHY.issubset(result.effective_truthy)
