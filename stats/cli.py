"""
    Desc: CLI to parse argument(s), collect statistics and print the report
    Creator: Kirosha
"""

import sys
import argparse

from stats import __version__
# importing the package registers all dialects
from stats import dialects
from stats.registry import get_dialect
from stats.render import render_table, render_json, render_md
from stats.stats import collect

RENDERERS = {
    "table": render_table,
    "json": render_json,
    "md": render_md
}

def _split(value: str | None) -> list[str]:
    items = []

    for item in (value or "").split(","):
        item = item.strip()
        if item and item not in items:
            items.append(item)

    return items

def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got: {value}")

    if number < 1: raise argparse.ArgumentTypeError("expected a number greater than zero")
    return number

def _non_negative(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got: {value}")

    if number < 0: raise argparse.ArgumentTypeError("expected a number greater than or equal to zero")
    return number

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stats",
        description="Print table and column statistics of a SQL database. Read-only."
    )

    parser.add_argument("--url", required=True, help='DSN, e.g. "postgresql://user:pass@host:5432/db"')
    parser.add_argument("--db", default="postgres", help="database from the dialect registry (default: postgres)")
    parser.add_argument("--schema", default="public", help="schema (default: public)")
    parser.add_argument("--table", help="comma-separated tables (default: all base tables of the schema)")
    parser.add_argument("--columns", help="comma-separated columns (default: all)")
    parser.add_argument("--format", choices=list(RENDERERS), default="table", help="report format (default: table)")
    parser.add_argument("--top", type=_non_negative, default=5, help="how many top values to show (default: 5, 0 disables)")
    parser.add_argument("--limit", type=_positive, default=None, help="count statistics over the first N rows of the table (sample)")
    parser.add_argument("--version", action="version", version=f"stats {__version__}")

    return parser

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    dialect = get_dialect(args.db)(args.url)

    try:
        stats = collect(
            dialect=dialect,
            schema=args.schema,
            tables=_split(args.table),
            columns=_split(args.columns),
            top=args.top,
            limit=args.limit
        )
    except Exception as err:
        print(f"failed to collect statistics: {err}", file=sys.stderr)
        return 1
    finally:
        dialect.close()

    if not stats:
        print(f"no tables or columns to report in schema {args.schema}", file=sys.stderr)
        return 1

    print(RENDERERS[args.format](stats))
    return 0

if __name__ == "__main__":
    sys.exit(main())
