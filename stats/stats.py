"""
    Desc: Functions to collect table statistics from a dialect
    Creator: Kirosha
"""

import sys

from stats.dialects.base import Dialect
from stats.models import ColumnStats, TableStats

# from this row count a full scan is considered heavy
LARGE_TABLE_ROWS = 1_000_000

def __warn(msg: str) -> None:
    print(msg, file=sys.stderr)

def collect_table(dialect: Dialect, table: str, schema: str, columns: list[str] | None = None, top: int = 5, limit: int | None = None) -> TableStats | None:
    metas = dialect.column_metadata(table, schema)

    if columns:
        found = [meta for meta in metas if meta.name in columns]

        missing = [name for name in columns if name not in [meta.name for meta in found]]
        if missing: __warn(f"таблица {table}: нет колонок {', '.join(missing)}")

        metas = found

    if not metas: return None

    row_count = dialect.table_row_count(table, schema)

    # the report is sampled only when the table really is bigger than the limit
    sampled = limit is not None and row_count > limit
    sample_limit = limit if sampled else None

    if limit is None and row_count > LARGE_TABLE_ROWS:
        __warn(f"таблица {table}: {row_count} строк, статистика по полной выборке; используйте --limit для сэмпла")

    return TableStats(
        name=table,
        schema=schema,
        row_count=row_count,
        sampled=sampled,
        sample_limit=sample_limit,
        columns=[
            ColumnStats(meta=meta, agg=dialect.column_aggregates(table, meta, schema, sample_limit, top))
            for meta in metas
        ]
    )

def collect(dialect: Dialect, schema: str, tables: list[str] | None = None, columns: list[str] | None = None, top: int = 5, limit: int | None = None) -> list[TableStats]:
    existing = dialect.list_tables(schema)

    if tables:
        missing = [table for table in tables if table not in existing]
        if missing: __warn(f"схема {schema}: нет таблиц {', '.join(missing)}")

        targets = [table for table in tables if table in existing]
    else:
        targets = existing

    result = []

    for table in targets:
        stats = collect_table(dialect, table, schema, columns, top, limit)
        if stats: result.append(stats)

    return result
