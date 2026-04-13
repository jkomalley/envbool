import pytest


@pytest.fixture(autouse=True)
def _reset_envbool_config():
    """Clear the envbool config cache after each test.

    Once config.py is implemented, change this to:
        yield
        envbool._reset_config()
    """
    return
