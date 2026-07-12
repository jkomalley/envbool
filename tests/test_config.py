"""Tests for _config.py: the in-memory EnvBoolConfig cache."""

import concurrent.futures
import dataclasses

import pytest

from envbool._config import EnvBoolConfig, _get_config, _reset_config, load_config
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY


class TestEnvBoolConfig:
    def test_defaults(self):
        config = EnvBoolConfig()
        assert config.strict is False
        assert config.warn is False
        assert config.effective_truthy == DEFAULT_TRUTHY
        assert config.effective_falsy == DEFAULT_FALSY

    def test_frozen(self):
        config = EnvBoolConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.strict = True  # type: ignore[misc]

    def test_effective_truthy_is_frozenset(self):
        assert isinstance(EnvBoolConfig().effective_truthy, frozenset)

    def test_effective_falsy_is_frozenset(self):
        assert isinstance(EnvBoolConfig().effective_falsy, frozenset)

    def test_custom_values(self):
        config = EnvBoolConfig(
            strict=True,
            warn=True,
            effective_truthy=frozenset({"yes"}),
            effective_falsy=frozenset({"no"}),
        )
        assert config.strict is True
        assert config.warn is True
        assert config.effective_truthy == frozenset({"yes"})
        assert config.effective_falsy == frozenset({"no"})


class TestConfigCache:
    def test_load_config_returns_defaults(self):
        assert load_config() == EnvBoolConfig()

    def test_same_instance_across_calls(self):
        assert load_config() is load_config()

    def test_load_config_and_get_config_return_same_instance(self):
        assert load_config() is _get_config()

    def test_reset_restores_defaults(self):
        first = load_config()
        _reset_config()
        second = load_config()
        assert first is not second
        assert second == EnvBoolConfig()


class TestConcurrentAccess:
    def test_concurrent_reads_see_one_instance(self):
        _reset_config()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: load_config(), range(32)))
        assert len({id(r) for r in results}) == 1
