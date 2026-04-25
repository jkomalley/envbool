"""Built-in truthy/falsy value sets -- the baseline when no overrides are provided.

These are intentionally small: common, unambiguous tokens only. Add project-specific
values like "enabled", "disabled", "y", "n" via extend_truthy / extend_falsy rather
than expecting them here.
"""
# Both _core.py and _config.py import these constants. Keeping them in a separate
# module prevents the circular import that would arise if _config.py imported from
# _core.py (which imports _get_config from _config.py).

__all__ = ["DEFAULT_FALSY", "DEFAULT_TRUTHY"]

DEFAULT_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "on"})
DEFAULT_FALSY: frozenset[str] = frozenset({"false", "0", "no", "off"})
