<h1 align="center">stats</h1>

<p align="center"><em>Read-only table and column statistics for a SQL database</em></p>

<div align="center">

[![Documentation](https://img.shields.io/badge/docs-online-4ade80?style=flat-square)](https://example.com/stats/docs/)
[![Python](https://img.shields.io/badge/language-Python-60a5fa?style=flat-square)]()
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-f87171?style=flat-square)]()
[![Output](https://img.shields.io/badge/output-table%20%7C%20json%20%7C%20md-a87ef5?style=flat-square)]()

</div>

---

stats connects to a SQL database and prints per-table and per-column statistics: row count, nulls, distinct values, min/max, mean, standard deviation, and top values.

**What stats is not.** It is read-only. It does not clean, migrate, or change anything: `SET default_transaction_read_only = on` runs right after connect, and there is no INSERT/UPDATE/DELETE/DDL in the code. Aggregates are computed on the database side; rows are never pulled into Python.

---

## Install

```bash
pip install -e ".[postgres]"
```

Python `3.10+`. The `psycopg[binary]>=3.1` driver is an extra (`postgres`) and is not needed to import the package. Without it the tool reports: `pip install 'stats[postgres]'`.

---

## Example

```bash
stats --url "$PG_URL" --schema dbstat_demo
stats --url "$PG_URL" --schema dbstat_demo --table users --columns age,status
stats --url "$PG_URL" --schema dbstat_demo --table orders --format json --limit 1000
```

Output for `--table users`:

```
schema: dbstat_demo

table: users  (row_count=1240, columns=5)
  id          integer      non_null=1240  null=0            distinct=1240  min=1                     max=1240                  mean=620.5  std=358.1
  email       text         non_null=1200  null=40 (3.2%)    distinct=1143  top: user10@example.com(2), user11@example.com(2), ...
  age         integer      non_null=981   null=259 (20.9%)  distinct=75    min=18                    max=92                    mean=55.29  std=21.63
  created_at  timestamptz  non_null=1240  null=0            distinct=1240  min=2023-01-03 05:00:00…  max=2024-12-27 20:00:00…
  status      text         non_null=1240  null=0            distinct=3     top: active(868), blocked(248), deleted(124)
```

---

## Flags

| Flag | Description |
|------|-------------|
| `--url` | DSN (required) |
| `--db` | database from the dialect registry, default `postgres` |
| `--schema` | schema, default `public` |
| `--table` | comma-separated tables, default all base tables of the schema (views are excluded) |
| `--columns` | comma-separated columns, default all |
| `--format` | `table` (default), `json`, `md` |
| `--top` | how many top values to show, default `5`, `0` disables |
| `--limit` | count statistics over the first N rows of the table |
| `--version` | print the version and exit |

Exit code: `0` on success, `1` if there are no tables or columns to report, or a query fails.

---

## Sampling (`--limit`)

`--limit N` enables sampling: if a table has more than N rows, statistics are computed over `SELECT * FROM t LIMIT N`, and the table header gets a `[sampled: limit=N]` mark (in json: `"sampled": true` and `"sample_limit": N`). **All column numbers (non_null, null, distinct, min, max, mean, std, top) refer to the sample, not the whole table.** Only `row_count` in the header is always real, computed with an honest `COUNT(*)`. The sample is taken without `ORDER BY`, i.e. "the first N rows that happen to come back", not a random sample. If the table has no more than N rows, there is no sampling and no mark.

Without `--limit`, tables with more than 1,000,000 rows get a warning on stderr, but the run continues.

---

## Format decisions

- `null=0` is always printed; `null=<n> (<pct>%)` with the percentage only when nulls exist.
- `mean` and `std` only for numeric columns. `std=-` when there are fewer than two values (`mean=-` for a column with no values).
- min/max and top values are cut to 20 characters in `table` and `md` (the last character is `…`); in `json` they are printed in full.
- Top values are printed comma-separated; a value is quoted if it contains a space or a comma.
- Top is computed only for text columns (not numeric, not date/time) and only when some value repeats; otherwise every count is 1. Such a column shows top instead of min/max.
- Types without ordering or equality (`json`, `point`, `boolean`, etc.) are counted with a retry via `::text`.
- In the report `timestamp with time zone` is printed as `timestamptz`, `character varying` as `varchar`. Time is printed in the session time zone.
- Columns inside a table keep their declared order; `--columns` only filters them. Missing tables and columns are skipped with a message on stderr.

---

## Test database

```bash
export PG_URL="postgresql://postgres:postgres@localhost:5432/postgres"
bash testdata/run_checks.sh
```

The script (needs `psql`) creates the `dbstat_demo` schema (idempotently), runs `stats`, and compares the report against `testdata/expected_users.txt`. Every line of that file is a regular expression that must match a line of the report. Seed values are deterministic formulas (no `random()`), so the numbers are exact. `created_at` is checked with a tolerance for the server time zone.

The seed produces 1240 users (40 without email, 259 without age, statuses: active 868 / blocked 248 / deleted 124) and 8300 orders.

---

## Project structure

```
stats/
├── pyproject.toml
├── README.md
├── stats/
│   ├── __init__.py          ← __version__
│   ├── models.py            ← ColumnMeta, ColumnAgg, ColumnStats, TableStats
│   ├── registry.py          ← register(), get_dialect(), available_dialects()
│   ├── stats.py             ← builds TableStats from a dialect
│   ├── render.py            ← render_table, render_json, render_md
│   ├── cli.py               ← argparse, main()
│   └── dialects/
│       ├── __init__.py      ← imports dialects for registration
│       ├── base.py          ← abc Dialect
│       └── postgres.py      ← PostgresDialect
└── testdata/
    ├── seed_postgres.sql
    ├── run_checks.sh
    └── expected_users.txt
```

---

## Adding a dialect

1. Create `stats/dialects/<name>.py` and a class inheriting `Dialect` decorated with `@register("<name>")`.
2. Implement 4 methods:
   - `list_tables(schema) -> list[str]`
   - `table_row_count(table, schema) -> int`
   - `column_metadata(table, schema) -> list[ColumnMeta]`
   - `column_aggregates(table, column, schema, limit, top) -> ColumnAgg`, where `column` is a `ColumnMeta` and `limit` is already resolved (`None` means no sample).
3. Add one import line to `stats/dialects/__init__.py`: `from stats.dialects import <name>`.
4. Add an extra with the driver to `pyproject.toml` (`[project.optional-dependencies]`).

Keep the driver import optional (as in `postgres.py`): the package must import without it, and the install hint must appear only on connect. Quote identifiers via the driver, pass values as parameters, never concatenate.

---

## Contributing

Contributions are welcome — open an issue or PR.

- **Keep it small.** stats is a single-purpose CLI. New features should solve a problem that can't be fixed by a dialect or a flag.
- **Match the style.** `__` for private members, utilities stay in their module, one class per responsibility.
- **One thing per PR.** Focused PRs merge faster.

If you're unsure whether an idea fits, open an issue first.

---

<p align="center"><sub>
<a href="https://example.com/stats/docs/">Docs</a> ·
<a href="https://github.com/example/stats/issues">Issues</a> ·
<a href="https://github.com/example/stats/releases">Releases</a>
</sub></p>