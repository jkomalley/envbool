import pytest

from envbool import reset_defaults


@pytest.fixture(autouse=True)
def _reset_envbool_defaults():
    """Reset process-level defaults after each test.

    Runs automatically for every test (autouse=True). Without this, a test
    that calls set_defaults() would leak its overrides into subsequent tests.
    """
    yield
    reset_defaults()
