"""
    Desc: Renderers to print statistics as text table, json or markdown
    Creator: Kirosha
"""

import json

from stats.models import ColumnStats, TableStats

# min, max and top values are cut to this length, the last character is the ellipsis
MAX_VALUE_LENGTH = 20

def __cut(value: str) -> str:
    value = value.replace("\r", " ").replace("\n", " ")
    if len(value) <= MAX_VALUE_LENGTH: return value
    return value[:MAX_VALUE_LENGTH - 1] + "…"

def __number(value: float | None) -> str:
    if value is None: return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".")

def __quote(value: str) -> str:
    cut = __cut(value)
    return f'"{cut}"' if " " in value or "," in value else cut

def __top(column: ColumnStats) -> str:
    return ", ".join(f"{__quote(value)}({count})" for value, count in column.agg.top_values)

def __null(column: ColumnStats) -> str:
    if not column.null_count: return "null=0"
    return f"null={column.null_count} ({column.null_pct:.1f}%)"

def __header(table: TableStats) -> str:
    header = f"table: {table.name}  (row_count={table.row_count}, columns={table.column_count})"
    if table.sampled: header += f"  [sampled: limit={table.sample_limit}]"
    return header

def __fields(column: ColumnStats) -> list[tuple[str, str]]:
    agg = column.agg

    fields = [
        ("non_null", f"non_null={agg.non_null}"),
        ("null", __null(column)),
        ("distinct", f"distinct={agg.distinct}")
    ]

    # a column with repeating values shows the top instead of min/max
    if agg.top_values:
        fields.append(("top", f"top: {__top(column)}"))
        return fields

    if agg.min_value is not None:
        fields.append(("min", f"min={__cut(agg.min_value)}"))
        fields.append(("max", f"max={__cut(agg.max_value)}"))

    if column.meta.is_numeric:
        fields.append(("mean", f"mean={__number(agg.mean)}"))
        fields.append(("std", f"std={__number(agg.std)}"))

    return fields

def __table_block(table: TableStats) -> list[str]:
    rows = [__fields(column) for column in table.columns]

    name_width = max(len(column.meta.name) for column in table.columns)
    type_width = max(len(column.meta.data_type) for column in table.columns)

    # every field is aligned by the widest one in the same column of the report
    widths = {}
    for fields in rows:
        for key, text in fields:
            widths[key] = max(widths.get(key, 0), len(text))

    lines = [__header(table)]

    for column, fields in zip(table.columns, rows):
        line = f"  {column.meta.name.ljust(name_width)}  {column.meta.data_type.ljust(type_width)}  "
        line += "  ".join(text.ljust(widths[key]) for key, text in fields)
        lines.append(line.rstrip())

    return lines

def render_table(stats_list: list[TableStats]) -> str:
    lines = []
    schema = None

    for table in stats_list:
        if table.schema != schema:
            schema = table.schema
            if lines: lines.append("")
            lines.append(f"schema: {schema}")

        lines.append("")
        lines += __table_block(table)

    return "\n".join(lines)

def __column_dict(column: ColumnStats) -> dict:
    agg = column.agg

    return {
        "name": column.meta.name,
        "type": column.meta.data_type,
        "nullable": column.meta.is_nullable,
        "non_null": agg.non_null,
        "null_count": column.null_count,
        "null_pct": round(column.null_pct, 2),
        "distinct": agg.distinct,
        "min": agg.min_value,
        "max": agg.max_value,
        "mean": agg.mean,
        "std": agg.std,
        "top": [{"value": value, "count": count} for value, count in agg.top_values]
    }

def render_json(stats_list: list[TableStats]) -> str:
    data = [
        {
            "schema": table.schema,
            "table": table.name,
            "row_count": table.row_count,
            "column_count": table.column_count,
            "sampled": table.sampled,
            "sample_limit": table.sample_limit,
            "columns": [__column_dict(column) for column in table.columns]
        }
        for table in stats_list
    ]

    return json.dumps(data, ensure_ascii=False, indent=2)

def __cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")

def __md_row(column: ColumnStats) -> str:
    agg = column.agg
    numeric = column.meta.is_numeric

    cells = [
        column.meta.name,
        column.meta.data_type,
        str(agg.non_null),
        "0" if not column.null_count else f"{column.null_count} ({column.null_pct:.1f}%)",
        str(agg.distinct),
        "-" if agg.min_value is None else __cut(agg.min_value),
        "-" if agg.max_value is None else __cut(agg.max_value),
        __number(agg.mean) if numeric else "-",
        __number(agg.std) if numeric else "-",
        __top(column) if agg.top_values else "-"
    ]

    return "| " + " | ".join(__cell(cell) for cell in cells) + " |"

def render_md(stats_list: list[TableStats]) -> str:
    blocks = []

    for table in stats_list:
        info = f"row_count={table.row_count}, columns={table.column_count}"
        if table.sampled: info += f" _(sampled: limit={table.sample_limit})_"

        lines = [
            f"### {table.schema}.{table.name}",
            "",
            info,
            "",
            "| column | type | non_null | null | distinct | min | max | mean | std | top |",
            "|---|---|---|---|---|---|---|---|---|---|"
        ]
        lines += [__md_row(column) for column in table.columns]

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
