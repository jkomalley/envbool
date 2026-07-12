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
  2  -- error (unrecognized value in strict mode, unset VAR_NAME with --required,
        bad arguments, multi-line stdin)

Omitting --strict or --warn defers to the config file setting (default:
lenient, no warnings).

Value sets: --truthy/--falsy (repeatable) replace the truthy/falsy set;
--extend-truthy/--extend-falsy (repeatable) add to it. Mirrors ruff's
select/extend-select pattern.

--show-config prints the effective configuration (config file path, strict,
warn, truthy, falsy) and exits. It can be combined with --strict/--truthy/
--falsy/--extend-truthy/--extend-falsy to preview overrides, but is mutually
exclusive with VAR_NAME, --value, --print, and --default.

Public surface:
    main()  -- entry point registered as the "envbool" command
"""
# --strict and --warn use default=None rather than False so an absent flag
# passes None through to envbool()/to_bool(), which then defers to the loaded
# config instead of overriding a config-level strict/warn = true with False.

__all__ = ["main"]

import argparse
import sys

from envbool._config import load_config
from envbool._core import _resolve, to_bool
from envbool._env import envbool
from envbool.exceptions import ConfigError, InvalidBoolValueError, MissingEnvVarError


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
        "--warn",
        action="store_true",
        # None so an absent flag defers to config rather than overriding it with False.
        default=None,
        help="Log a warning on unrecognized values.",
    )
    parser.add_argument(
        "--default",
        "-d",
        action="store_true",
        default=False,
        help="Default value if unset/empty (default: false).",
    )
    parser.add_argument(
        "--required",
        "-r",
        action="store_true",
        default=False,
        help="Exit 2 if VAR_NAME is not set in the environment.",
    )
    parser.add_argument(
        "--print",
        "-p",
        dest="print_result",
        action="store_true",
        help='Print "true" or "false" instead of using exit codes.',
    )
    parser.add_argument(
        "--truthy",
        metavar="VALUE",
        action="append",
        help="Replace the truthy set with VALUE (repeatable).",
    )
    parser.add_argument(
        "--falsy",
        metavar="VALUE",
        action="append",
        help="Replace the falsy set with VALUE (repeatable).",
    )
    parser.add_argument(
        "--extend-truthy",
        metavar="VALUE",
        action="append",
        help="Add VALUE to the truthy set (repeatable).",
    )
    parser.add_argument(
        "--extend-falsy",
        metavar="VALUE",
        action="append",
        help="Add VALUE to the falsy set (repeatable).",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print the effective configuration and exit.",
    )
    return parser


def _print_config(args: argparse.Namespace) -> None:
    """Print the effective configuration, reflecting any CLI overrides."""
    config = load_config()
    effective_truthy, effective_falsy = _resolve(
        config_truthy=config.effective_truthy,
        config_falsy=config.effective_falsy,
        truthy=args.truthy,
        falsy=args.falsy,
        extend_truthy=args.extend_truthy,
        extend_falsy=args.extend_falsy,
    )
    effective_strict = args.strict if args.strict is not None else config.strict
    effective_warn = args.warn if args.warn is not None else config.warn

    print(f"config file: {config.source_path or 'none'}")
    print(f"strict:      {str(effective_strict).lower()}")
    print(f"warn:        {str(effective_warn).lower()}")
    print(f"truthy:      {', '.join(sorted(effective_truthy))}")
    print(f"falsy:       {', '.join(sorted(effective_falsy))}")


def _coerce_from_source(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> bool:
    """Resolve the input source (--value, VAR_NAME, or stdin) and coerce it to bool.

    Validates the mutually exclusive source flags, then dispatches to the matching
    coercion call. Exits via parser.error()/sys.exit() for usage errors; the
    coercion exceptions propagate to main()'s single error boundary.
    """
    value_set_kwargs = {
        "truthy": args.truthy,
        "falsy": args.falsy,
        "extend_truthy": args.extend_truthy,
        "extend_falsy": args.extend_falsy,
    }

    # --value and VAR_NAME are mutually exclusive. Using argparse's built-in
    # add_mutually_exclusive_group would place them in a separate usage section,
    # which makes the help text harder to read, so we validate manually instead.
    if args.value is not None and args.var is not None:
        parser.error("VAR_NAME and --value are mutually exclusive")

    # --required only governs the env-var lookup; a literal --value always
    # has a value, so combining them is a usage error rather than a no-op.
    if args.required and args.value is not None:
        parser.error("--required and --value are mutually exclusive")

    # --required only makes sense against an env var lookup; reject it whenever
    # there's no VAR_NAME to be "required" -- covers both the stdin-pipe path and
    # the case where neither --value nor VAR_NAME nor stdin was given.
    if args.required and args.var is None:
        parser.error("--required requires VAR_NAME")

    if args.value is not None:
        return to_bool(
            args.value,
            strict=args.strict,
            warn=args.warn,
            default=args.default,
            **value_set_kwargs,
        )
    if args.var is not None:
        return envbool(
            args.var,
            strict=args.strict,
            warn=args.warn,
            default=args.default,
            required=args.required,
            **value_set_kwargs,
        )
    if not sys.stdin.isatty():
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
        # Empty stdin (e.g. `envbool </dev/null` under cron/CI with a forgotten
        # VAR_NAME) is "no source applies", not "the value is empty" -- fall
        # through to the usage/exit-2 path below rather than silently coercing.
        if raw:
            return to_bool(
                raw,
                strict=args.strict,
                warn=args.warn,
                default=args.default,
                **value_set_kwargs,
            )

    parser.print_usage(sys.stderr)
    sys.exit(2)


def main() -> None:
    """Parse arguments, resolve the input source, and exit with the appropriate code."""
    # All coercion logic lives in _core.py; this function is pure I/O plumbing.
    parser = _build_parser()
    args = parser.parse_args()

    # Both --show-config and the coercion calls below trigger config-file loading,
    # so a malformed config can raise ConfigError from either path. A single error
    # boundary around both keeps that failure a clean "error: ..." exit rather than
    # an uncaught traceback. parser.error() and sys.exit() raise SystemExit, which
    # is not caught here and so propagates as intended.
    try:
        if args.show_config:
            conflicting = (
                args.var is not None
                or args.value is not None
                or args.print_result
                or args.default
                or args.required
            )
            if conflicting:
                parser.error(
                    "--show-config is mutually exclusive with VAR_NAME, --value, "
                    "--print, --default, and --required"
                )
            _print_config(args)
            sys.exit(0)

        result = _coerce_from_source(parser, args)
    except (InvalidBoolValueError, ConfigError, MissingEnvVarError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    if args.print_result:
        print("true" if result else "false")
        sys.exit(0)
    else:
        sys.exit(0 if result else 1)
