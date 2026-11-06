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
        raise argparse.ArgumentTypeError(f"нужно целое число, получено: {value}")

    if number < 1: raise argparse.ArgumentTypeError("нужно число больше нуля")
    return number

def _non_negative(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"нужно целое число, получено: {value}")

    if number < 0: raise argparse.ArgumentTypeError("нужно число не меньше нуля")
    return number

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stats",
        description="Печатает статистику по таблицам и колонкам SQL-базы. Только читает данные."
    )

    parser.add_argument("--url", required=True, help='DSN, например "postgresql://user:pass@host:5432/db"')
    parser.add_argument("--db", default="postgres", help="СУБД из реестра диалектов (по умолчанию postgres)")
    parser.add_argument("--schema", default="public", help="схема (по умолчанию public)")
    parser.add_argument("--table", help="таблицы через запятую (по умолчанию все базовые таблицы схемы)")
    parser.add_argument("--columns", help="колонки через запятую (по умолчанию все)")
    parser.add_argument("--format", choices=list(RENDERERS), default="table", help="формат отчёта (по умолчанию table)")
    parser.add_argument("--top", type=_non_negative, default=5, help="сколько топ-значений показывать (по умолчанию 5, 0 отключает)")
    parser.add_argument("--limit", type=_positive, default=None, help="считать статистику по первым N строкам таблицы (сэмпл)")
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
        print(f"Ошибка при сборе статистики: {err}", file=sys.stderr)
        return 1
    finally:
        dialect.close()

    if not stats:
        print(f"В схеме {args.schema} нет таблиц или колонок для статистики", file=sys.stderr)
        return 1

    print(RENDERERS[args.format](stats))
    return 0

if __name__ == "__main__":
    sys.exit(main())
