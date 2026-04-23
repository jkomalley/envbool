"""Tests for core.py: DEFAULT_TRUTHY, DEFAULT_FALSY, and _resolve."""

from envbool.core import DEFAULT_FALSY, DEFAULT_TRUTHY, _resolve


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
