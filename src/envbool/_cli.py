"""envbool CLI -- coerce an environment variable or string to a boolean.

Usage: envbool [OPTIONS] [VAR_NAME]

Input source (first match wins):
  1. --value TEXT  -- coerce a literal string directly
  2. VAR_NAME      -- read and coerce an environment variable
  3. stdin pipe    -- read a single value from stdin (piped or redirected)
  If none apply, prints usage and exits 2.

Exit codes:
  0  -- truthy
  1  -- falsy or unset/empty
  2  -- error (unrecognized value in strict mode, bad arguments, multi-line stdin)

Omitting --strict defers to the config file setting (default: lenient).

Public surface:
    main()  -- entry point registered as the "envbool" command
"""
# --strict uses default=None rather than False so an absent flag passes None
# through to envbool()/to_bool(), which then defers to the loaded config
# instead of overriding a config-level strict = true with False.

__all__ = ["main"]

import argparse
import sys

from envbool._core import to_bool
from envbool._env import envbool
from envbool.exceptions import InvalidBoolValueError


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    # Separated from main() so tests can call it directly without going through
    # the full parse-and-exit cycle.
    parser = argparse.ArgumentParser(
        prog="envbool",
        description="Coerce an environment variable or string to a boolean.",
    )
    parser.add_argument(
        "var",
        nargs="?",
        metavar="VAR_NAME",
        help="Environment variable name to check.",
    )
    parser.add_argument(
        "--value",
        "-v",
        metavar="TEXT",
        help="Check a literal string instead of an env var.",
    )
    parser.add_argument(
        "--strict",
        "-s",
        action="store_true",
        # None so an absent flag defers to config rather than overriding it with False.
        # store_true with default=None gives: flag present -> True, absent -> None.
        default=None,
        help="Raise error on unrecognized values.",
    )
    parser.add_argument(
        "--default",
        "-d",
        action="store_true",
        default=False,
        help="Default value if unset/empty (default: false).",
    )
    parser.add_argument(
        "--print",
        "-p",
        dest="print_result",
        action="store_true",
        help='Print "true" or "false" instead of using exit codes.',
    )
    return parser


def main() -> None:
    """Parse arguments, resolve the input source, and exit with the appropriate code."""
    # All coercion logic lives in _core.py; this function is pure I/O plumbing.
    parser = _build_parser()
    args = parser.parse_args()

    # --value and VAR_NAME are mutually exclusive. Using argparse's built-in
    # add_mutually_exclusive_group would place them in a separate usage section,
    # which makes the help text harder to read, so we validate manually instead.
    if args.value is not None and args.var is not None:
        parser.error("VAR_NAME and --value are mutually exclusive")

    try:
        if args.value is not None:
            result = to_bool(args.value, strict=args.strict, default=args.default)
        elif args.var is not None:
            result = envbool(args.var, strict=args.strict, default=args.default)
        elif not sys.stdin.isatty():
            # Non-TTY stdin means the user piped or redirected input. Strip surrounding
            # whitespace (handles the trailing newline echo adds) then reject anything
            # with an embedded newline -- only a single value is meaningful here.
            raw = sys.stdin.read().strip()
            if "\n" in raw:
                print(
                    "error: stdin must contain a single value, not multiple lines",
                    file=sys.stderr,
                )
                sys.exit(2)
            result = to_bool(raw, strict=args.strict, default=args.default)
        else:
            parser.print_usage(sys.stderr)
            sys.exit(2)
    except InvalidBoolValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    if args.print_result:
        print("true" if result else "false")
        sys.exit(0)
    else:
        sys.exit(0 if result else 1)
