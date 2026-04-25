"""Tests for config.py: discovery, parsing, caching, and to_bool integration."""

import concurrent.futures
import dataclasses
import logging
from unittest.mock import patch

import pytest

import envbool
from envbool._config import (
    EnvBoolConfig,
    _get_config,
    _load_config_from_disk,
    _reset_config,
    load_config,
)
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY
from envbool.exceptions import ConfigError, EnvBoolError, InvalidBoolValueError

# ---------------------------------------------------------------------------
# EnvBoolConfig dataclass
# ---------------------------------------------------------------------------


class TestEnvBoolConfig:
    def test_defaults(self):
        config = EnvBoolConfig()
        assert config.strict is False
        assert config.warn is False
        assert config.effective_truthy == DEFAULT_TRUTHY
        assert config.effective_falsy == DEFAULT_FALSY
        assert config.source_path is None

    def test_frozen(self):
        config = EnvBoolConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.strict = True  # type: ignore[misc]

    def test_effective_truthy_is_frozenset(self):
        assert isinstance(EnvBoolConfig().effective_truthy, frozenset)

    def test_effective_falsy_is_frozenset(self):
        assert isinstance(EnvBoolConfig().effective_falsy, frozenset)

    def test_custom_values(self, tmp_path):
        config = EnvBoolConfig(
            strict=True,
            warn=True,
            effective_truthy=frozenset({"yes"}),
            effective_falsy=frozenset({"no"}),
            source_path=tmp_path / "envbool.toml",
        )
        assert config.strict is True
        assert config.warn is True
        assert config.effective_truthy == frozenset({"yes"})
        assert config.effective_falsy == frozenset({"no"})
        assert config.source_path == tmp_path / "envbool.toml"


# ---------------------------------------------------------------------------
# Discovery: envbool.toml
# ---------------------------------------------------------------------------


class TestDiscoveryEnvboolToml:
    def test_finds_in_cwd(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.strict is True
        assert config.source_path == tmp_path / "envbool.toml"

    def test_finds_in_parent(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        config = load_config()
        assert config.warn is True
        assert config.source_path == tmp_path / "envbool.toml"

    def test_envbool_toml_beats_pyproject_in_same_dir(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.envbool]\nstrict = false\nwarn = true\n"
        )
        monkeypatch.chdir(tmp_path)
        config = load_config()
        # envbool.toml wins; pyproject.toml values not applied
        assert config.strict is True
        assert config.warn is False

    def test_source_path_is_absolute(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("")
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.source_path is not None
        assert config.source_path.is_absolute()


# ---------------------------------------------------------------------------
# Discovery: pyproject.toml [tool.envbool]
# ---------------------------------------------------------------------------


class TestDiscoveryPyprojectToml:
    def test_finds_tool_envbool_section(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text("[tool.envbool]\nstrict = true\n")
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.strict is True
        assert config.source_path == tmp_path / "pyproject.toml"

    def test_pyproject_without_section_stops_walk_no_config(
        self, tmp_path, monkeypatch
    ):
        # pyproject.toml with no [tool.envbool] section -- stops walk, returns defaults
        parent = tmp_path / "parent"
        parent.mkdir()
        child = parent / "child"
        child.mkdir()
        # Put an envbool.toml in the grandparent (should NOT be found because
        # pyproject.toml in parent stops the walk)
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        # pyproject.toml in parent with no envbool section
        (parent / "pyproject.toml").write_text('[tool.other]\nkey = "value"\n')
        monkeypatch.chdir(child)
        config = load_config()
        # The walk stopped at parent/pyproject.toml, so strict=True from grandparent
        # envbool.toml was never found.
        assert config.strict is False
        assert config.source_path is None

    def test_finds_section_in_parent_pyproject(self, tmp_path, monkeypatch):
        subdir = tmp_path / "src"
        subdir.mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.envbool]\nwarn = true\n")
        monkeypatch.chdir(subdir)
        config = load_config()
        assert config.warn is True


# ---------------------------------------------------------------------------
# Discovery: boundary markers
# ---------------------------------------------------------------------------


class TestDiscoveryBoundaryMarkers:
    @pytest.mark.parametrize("marker", [".git", ".hg", "setup.py", "setup.cfg"])
    def test_marker_stops_walk(self, tmp_path, monkeypatch, marker):
        # envbool.toml above the marker should NOT be found
        grandparent = tmp_path
        parent = grandparent / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        (grandparent / "envbool.toml").write_text("strict = true\n")
        # Place the boundary marker in parent
        marker_path = parent / marker
        if marker in (".git", ".hg"):
            marker_path.mkdir()
        else:
            marker_path.touch()
        monkeypatch.chdir(child)
        config = load_config()
        # Marker stopped the walk before reaching grandparent
        assert config.strict is False
        assert config.source_path is None

    @pytest.mark.parametrize("marker", [".git", ".hg", "setup.py", "setup.cfg"])
    def test_config_in_same_dir_as_marker_is_found(self, tmp_path, monkeypatch, marker):
        # Config file in the same directory as the marker should still be discovered
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        marker_path = tmp_path / marker
        if marker in (".git", ".hg"):
            marker_path.mkdir()
        else:
            marker_path.touch()
        monkeypatch.chdir(subdir)
        config = load_config()
        assert config.warn is True


# ---------------------------------------------------------------------------
# Discovery: depth cap
# ---------------------------------------------------------------------------


class TestDiscoveryDepthCap:
    def test_stops_after_ten_levels(self, tmp_path, monkeypatch):
        # Build a 12-level directory tree with no markers
        deep = tmp_path
        for i in range(12):
            deep = deep / f"d{i}"
        deep.mkdir(parents=True)
        # Put config at the root -- it's more than 10 levels up
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(deep)
        config = load_config()
        # Too deep to be found; defaults apply
        assert config.strict is False
        assert config.source_path is None

    def test_finds_config_within_ten_levels(self, tmp_path, monkeypatch):
        # 9 levels deep -- config at root should be found
        deep = tmp_path
        for i in range(9):
            deep = deep / f"d{i}"
        deep.mkdir(parents=True)
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(deep)
        config = load_config()
        assert config.strict is True


# ---------------------------------------------------------------------------
# Discovery: ENVBOOL_NO_CONFIG and missing files
# ---------------------------------------------------------------------------


class TestDiscoveryNoConfig:
    def test_no_config_env_skips_discovery(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "1")
        config = load_config()
        assert config.strict is False
        assert config.source_path is None

    def test_no_config_env_zero_does_not_skip(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVBOOL_NO_CONFIG", "0")
        config = load_config()
        assert config.strict is True

    def test_missing_files_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config == EnvBoolConfig()

    def test_platformdirs_failure_falls_back_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch(
            "envbool._config.platformdirs.user_config_dir",
            side_effect=Exception("boom"),
        ):
            config = load_config()
        assert config == EnvBoolConfig()


# ---------------------------------------------------------------------------
# Discovery: user-level config via platformdirs
# ---------------------------------------------------------------------------


class TestDiscoveryUserLevel:
    def test_falls_back_to_user_config(self, tmp_path, monkeypatch):
        user_config_dir = tmp_path / "user_config" / "envbool"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text("warn = true\n")

        # No project-level config; CWD has no markers
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        with patch(
            "envbool._config.platformdirs.user_config_dir",
            return_value=str(user_config_dir),
        ):
            config = load_config()

        assert config.warn is True
        assert config.source_path == user_config_dir / "config.toml"

    def test_project_config_wins_over_user_config(self, tmp_path, monkeypatch):
        user_config_dir = tmp_path / "user_config" / "envbool"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text("strict = true\n")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "envbool.toml").write_text("strict = false\n")
        monkeypatch.chdir(project_dir)

        with patch(
            "envbool._config.platformdirs.user_config_dir",
            return_value=str(user_config_dir),
        ):
            config = load_config()

        # Project config wins; user config's strict=true is ignored
        assert config.strict is False
        assert config.source_path == project_dir / "envbool.toml"

    def test_missing_user_config_file_returns_defaults(self, tmp_path, monkeypatch):
        user_config_dir = tmp_path / "user_config" / "envbool"
        user_config_dir.mkdir(parents=True)
        # No config.toml in user dir

        project = tmp_path / "project"
        monkeypatch.chdir(project if project.exists() else tmp_path)

        with patch(
            "envbool._config.platformdirs.user_config_dir",
            return_value=str(user_config_dir),
        ):
            config = load_config()

        assert config == EnvBoolConfig()


# ---------------------------------------------------------------------------
# Config parsing: extend/replace, strict, warn, unknown keys
# ---------------------------------------------------------------------------


class TestConfigParsing:
    def test_truthy_replaces_defaults(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('truthy = ["si", "oui"]\n')
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.effective_truthy == frozenset({"si", "oui"})
        # Default truthy values are gone
        assert "true" not in config.effective_truthy

    def test_extend_truthy_adds_to_defaults(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('extend_truthy = ["enabled", "y"]\n')
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert "true" in config.effective_truthy
        assert "enabled" in config.effective_truthy
        assert "y" in config.effective_truthy

    def test_truthy_wins_over_extend_truthy(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text(
            'truthy = ["1"]\nextend_truthy = ["enabled"]\n'
        )
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.effective_truthy == frozenset({"1"})

    def test_falsy_replaces_defaults(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('falsy = ["nope"]\n')
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.effective_falsy == frozenset({"nope"})
        assert "false" not in config.effective_falsy

    def test_extend_falsy_adds_to_defaults(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('extend_falsy = ["disabled"]\n')
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert "false" in config.effective_falsy
        assert "disabled" in config.effective_falsy

    def test_falsy_wins_over_extend_falsy(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text(
            'falsy = ["nope"]\nextend_falsy = ["disabled"]\n'
        )
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.effective_falsy == frozenset({"nope"})

    def test_strict_propagates(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        assert load_config().strict is True

    def test_warn_propagates(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        monkeypatch.chdir(tmp_path)
        assert load_config().warn is True

    def test_unknown_keys_are_ignored(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text(
            'strict = true\nfuture_option = "whatever"\n'
        )
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.strict is True  # known key parsed correctly

    def test_empty_truthy_list_is_valid(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("truthy = []\n")
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.effective_truthy == frozenset()

    def test_pyproject_section_parsed_correctly(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.envbool]\nstrict = true\nextend_truthy = ["enabled"]\n'
        )
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config.strict is True
        assert "enabled" in config.effective_truthy
        assert "true" in config.effective_truthy  # default truthy still present


# ---------------------------------------------------------------------------
# Config validation: type errors and malformed TOML
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_malformed_toml_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = [not valid\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert exc_info.value.path == tmp_path / "envbool.toml"

    def test_strict_wrong_type_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('strict = "yes"\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert exc_info.value.path == tmp_path / "envbool.toml"
        assert "strict" in str(exc_info.value)

    def test_warn_wrong_type_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("warn = 1\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert "warn" in str(exc_info.value)

    def test_truthy_not_a_list_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('truthy = "yes"\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert "truthy" in str(exc_info.value)

    def test_truthy_list_with_non_string_raises_config_error(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "envbool.toml").write_text('truthy = ["yes", 1]\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert "truthy" in str(exc_info.value)

    def test_extend_falsy_not_a_list_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("extend_falsy = false\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert "extend_falsy" in str(exc_info.value)

    def test_config_error_inherits_from_envbool_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('strict = "bad"\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(EnvBoolError):
            load_config()

    def test_config_error_not_value_error(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('strict = "bad"\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError):
            load_config()
        # ConfigError must NOT be a ValueError
        assert not issubclass(ConfigError, ValueError)

    def test_malformed_pyproject_toml_raises_config_error(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text("[tool.envbool\nbroken\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert exc_info.value.path == tmp_path / "pyproject.toml"

    def test_pyproject_tool_envbool_not_a_table_raises_config_error(
        self, tmp_path, monkeypatch
    ):
        # [tool] envbool = "string" is valid TOML but [tool.envbool] must be a table
        (tmp_path / "pyproject.toml").write_text('[tool]\nenvbool = "not a table"\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        assert exc_info.value.path == tmp_path / "pyproject.toml"


# ---------------------------------------------------------------------------
# Config value normalization
# ---------------------------------------------------------------------------


class TestConfigNormalization:
    def test_config_truthy_values_are_lowercased(self, tmp_path, monkeypatch):
        # Values from the config file must be normalized so they match the
        # lowercased input that to_bool() produces.
        (tmp_path / "envbool.toml").write_text('truthy = ["Enabled", "YES"]\n')
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("Enabled") is True
        assert envbool.to_bool("YES") is True
        assert envbool.to_bool("enabled") is True

    def test_config_truthy_values_are_stripped(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('truthy = ["  enabled  "]\n')
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("enabled") is True

    def test_config_extend_truthy_values_are_normalized(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('extend_truthy = ["Enabled"]\n')
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("enabled") is True
        assert envbool.to_bool("true") is True  # default still present

    def test_config_falsy_values_are_normalized(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('falsy = ["NOPE"]\nstrict = true\n')
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("nope", strict=True) is False

    def test_call_site_truthy_values_are_normalized(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("enabled", truthy={"Enabled"}) is True
        assert envbool.to_bool("enabled", extend_truthy={"ENABLED"}) is True

    def test_call_site_falsy_values_are_normalized(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("nope", falsy={"NOPE"}, strict=True) is False
        assert envbool.to_bool("nope", extend_falsy={"Nope"}, strict=True) is False


# ---------------------------------------------------------------------------
# load_config / _get_config: caching
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_envbool_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert isinstance(load_config(), EnvBoolConfig)

    def test_source_path_none_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert load_config().source_path is None

    def test_source_path_set_when_file_found(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("")
        monkeypatch.chdir(tmp_path)
        assert load_config().source_path == tmp_path / "envbool.toml"

    def test_cached_after_first_call(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch(
            "envbool._config._load_config_from_disk",
            wraps=_load_config_from_disk,
        ) as mock_load:
            load_config()
            load_config()
            load_config()
        assert mock_load.call_count == 1

    def test_load_config_and_get_config_return_same_instance(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        assert load_config() is _get_config()


# ---------------------------------------------------------------------------
# _reset_config
# ---------------------------------------------------------------------------


class TestResetConfig:
    def test_reset_clears_cache(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = load_config()
        _reset_config()
        second = load_config()
        # Both should be equal (same defaults) but must be new objects
        assert first == second
        assert first is not second

    def test_reset_allows_config_file_change_to_take_effect(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        first = load_config()
        assert first.strict is False

        # Write a config file, reset, and reload
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        _reset_config()
        second = load_config()
        assert second.strict is True


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    def test_only_one_disk_read_under_concurrent_first_access(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        call_count = []

        original = _load_config_from_disk

        def counting_load():
            call_count.append(1)
            return original()

        # ThreadPoolExecutor.result() re-raises any exception from the worker,
        # so test failures surface cleanly rather than being silently swallowed.
        with (
            patch("envbool._config._load_config_from_disk", side_effect=counting_load),
            concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor,
        ):
            futures = [executor.submit(_get_config) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 10
        # All threads should have received the same config object
        assert all(r is results[0] for r in results)
        # Disk was read exactly once despite 10 concurrent threads
        assert len(call_count) == 1


# ---------------------------------------------------------------------------
# to_bool integration with config
# ---------------------------------------------------------------------------


class TestToBoolUsesConfig:
    def test_strict_none_defers_to_config_true(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(InvalidBoolValueError):
            envbool.to_bool("maybe")

    def test_strict_none_defers_to_config_false(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = false\n")
        monkeypatch.chdir(tmp_path)
        # Should not raise -- lenient mode
        assert envbool.to_bool("maybe") is False

    def test_strict_true_overrides_config_false(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = false\n")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(InvalidBoolValueError):
            envbool.to_bool("maybe", strict=True)

    def test_strict_false_overrides_config_true(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text("strict = true\n")
        monkeypatch.chdir(tmp_path)
        # strict=False at call site overrides config
        assert envbool.to_bool("maybe", strict=False) is False

    def test_warn_none_defers_to_config(self, tmp_path, monkeypatch, caplog):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool.to_bool("maybe")
        assert any("maybe" in r.message for r in caplog.records)

    def test_warn_false_overrides_config_true(self, tmp_path, monkeypatch, caplog):
        (tmp_path / "envbool.toml").write_text("warn = true\n")
        monkeypatch.chdir(tmp_path)
        with caplog.at_level(logging.WARNING, logger="envbool._core"):
            envbool.to_bool("maybe", warn=False)
        # No warning should have been emitted
        assert not any("maybe" in r.message for r in caplog.records)

    def test_config_truthy_used_when_no_call_arg(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('truthy = ["enabled"]\n')
        monkeypatch.chdir(tmp_path)
        # "enabled" is in config truthy; "true" is NOT (config replaces defaults)
        assert envbool.to_bool("enabled") is True
        assert envbool.to_bool("true") is False

    def test_function_extend_truthy_extends_config_resolved_set(
        self, tmp_path, monkeypatch
    ):
        # Config adds "enabled" to defaults; call site adds "y" on top of that.
        # Function-level extend_truthy must extend the config-resolved set, not
        # just the hardcoded defaults.
        (tmp_path / "envbool.toml").write_text('extend_truthy = ["enabled"]\n')
        monkeypatch.chdir(tmp_path)
        assert envbool.to_bool("y", extend_truthy={"y"}) is True
        assert envbool.to_bool("enabled", extend_truthy={"y"}) is True
        assert envbool.to_bool("true", extend_truthy={"y"}) is True

    def test_function_truthy_replaces_config_resolved_set(self, tmp_path, monkeypatch):
        (tmp_path / "envbool.toml").write_text('extend_truthy = ["enabled"]\n')
        monkeypatch.chdir(tmp_path)
        # Call-site truthy= replaces everything, including the config's "enabled"
        assert envbool.to_bool("only", truthy={"only"}) is True
        assert envbool.to_bool("enabled", truthy={"only"}) is False
        assert envbool.to_bool("true", truthy={"only"}) is False
