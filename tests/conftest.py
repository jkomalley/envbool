import pytest

from envbool._config import _reset_config


@pytest.fixture(autouse=True)
def _reset_envbool_config():
    """Clear the envbool config cache before each test.

    Runs automatically for every test (autouse=True). Without this, a test that
    triggers config loading would pollute the global cache and cause subsequent
    tests to see stale config rather than re-discovering from their own tmp_path.
    """
    yield
    _reset_config()
