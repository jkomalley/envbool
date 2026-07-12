import pytest

from envbool._config import _reset_config


@pytest.fixture(autouse=True)
def _reset_envbool_config():
    """Reset the envbool config cache after each test.

    Runs automatically for every test (autouse=True). Without this, a test
    that mutates the process-level config would leak state into subsequent
    tests instead of leaving them a fresh, default-built EnvBoolConfig.
    """
    yield
    _reset_config()
