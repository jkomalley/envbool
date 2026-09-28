"""Tests for the public envbool package surface."""

import pytest

import envbool


def test_all_lists_public_api():
    assert set(envbool.__all__) == {
        "DEFAULT_FALSY",
        "DEFAULT_TRUTHY",
        "ConflictingValuesError",
        "EnvBoolError",
        "InvalidBoolValueError",
        "MissingEnvVarError",
        "envbool",
        "to_bool",
    }


@pytest.mark.parametrize(
    "name", ["set_defaults", "get_defaults", "reset_defaults", "Defaults"]
)
def test_no_process_wide_defaults_api(name):
    # envbool has no process-wide state; guard against re-exporting it.
    assert not hasattr(envbool, name)
