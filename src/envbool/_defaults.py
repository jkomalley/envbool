"""Built-in truthy/falsy value sets -- single source of truth for the whole package.

Both core.py and config.py need these constants. Keeping them here prevents the
circular import that would arise if config.py imported from core.py (which imports
from config.py for _get_config).

These are the baseline used when no config file is present and no call-site
overrides are provided. They are intentionally small -- common, unambiguous tokens
only. Users can add "y", "n", "enabled", "disabled", etc. via extend_truthy /
extend_falsy.
"""

__all__ = ["DEFAULT_FALSY", "DEFAULT_TRUTHY"]

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})
