"""
    Desc: PostgresDialect class to read statistics from PostgreSQL, read-only
    Creator: Kirosha
"""

# the driver is optional, the package must be importable without it
try:
    import psycopg
    from psycopg import sql
except ImportError:
    psycopg = None
    sql = None

from stats.models import ColumnMeta, ColumnAgg
from stats.registry import register
from stats.dialects.base import Dialect

# data types (information_schema) that are counted as numeric
NUMERIC_TYPES = frozenset({
    "smallint", "integer", "bigint", "decimal", "numeric",
    "real", "double precision", "float4", "float8"
})

# short names (see TYPE_ALIASES) of types where min/max is more useful than the top values
TEMPORAL_TYPES = frozenset({"date", "time", "timetz", "timestamp", "timestamptz", "interval"})

# long names of information_schema to short names of the report
TYPE_ALIASES = {
    "timestamp with time zone": "timestamptz",
    "timestamp without time zone": "timestamp",
    "time with time zone": "timetz",
    "time without time zone": "time",
    "character varying": "varchar",
    "character": "char"
}

READ_ONLY = "SET default_transaction_read_only = on"

@register("postgres")
class PostgresDialect(Dialect):
    def __fetch(self, query, params: tuple | None = None) -> list[tuple]:
        with self.__connection.cursor() as cursor:
            cursor.execute(query, params or None)
            return cursor.fetchall()

    def __source(self, table: str, schema: str, limit: int | None) -> tuple:
        relation = sql.SQL("{schema}.{table}").format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table)
        )
        if limit is None: return relation, ()

        source = sql.SQL("(SELECT * FROM {relation} LIMIT %s) AS s").format(relation=relation)
        return source, (limit,)

    def __expression(self, column: str, as_text: bool):
        # types without ordering or equality (json, xml, ...) are compared as text
        if as_text: return sql.SQL("{col}::text").format(col=sql.Identifier(column))
        return sql.Identifier(column)

    def __top_values(self, source, params: tuple, column: ColumnMeta, as_text: bool, top: int) -> list[tuple[str, int]]:
        query = sql.SQL(
            "SELECT {col}::text AS v, COUNT(*) FROM {source} WHERE {col} IS NOT NULL "
            "GROUP BY {expr} ORDER BY COUNT(*) DESC, v LIMIT %s"
        ).format(
            col=sql.Identifier(column.name),
            source=source,
            expr=self.__expression(column.name, as_text)
        )

        rows = self.__fetch(query, (*params, top))
        return [(str(value), int(count)) for value, count in rows]

    def __aggregate(self, source, params: tuple, column: ColumnMeta, as_text: bool, top: int) -> ColumnAgg:
        col = sql.Identifier(column.name)
        expr = self.__expression(column.name, as_text)

        parts = [
            sql.SQL("COUNT(*)"),
            sql.SQL("COUNT({col})").format(col=col),
            sql.SQL("COUNT(DISTINCT {expr})").format(expr=expr),
            sql.SQL("MIN({expr})::text").format(expr=expr),
            sql.SQL("MAX({expr})::text").format(expr=expr)
        ]

        if column.is_numeric:
            parts += [
                sql.SQL("AVG({col})").format(col=col),
                sql.SQL("STDDEV_SAMP({col})").format(col=col)
            ]

        query = sql.SQL("SELECT {fields} FROM {source}").format(
            fields=sql.SQL(", ").join(parts),
            source=source
        )

        row = self.__fetch(query, params)[0]
        count, non_null, distinct = int(row[0]), int(row[1]), int(row[2])

        mean = std = None
        if column.is_numeric:
            mean = None if row[5] is None else float(row[5])
            std = None if row[6] is None else float(row[6])

        # top values are for text-like columns, and only if some value repeats (otherwise every count is 1)
        top_values = []
        if top > 0 and not column.is_numeric and column.data_type not in TEMPORAL_TYPES and distinct < non_null:
            top_values = self.__top_values(source, params, column, as_text, top)

        return ColumnAgg(
            count=count,
            non_null=non_null,
            distinct=distinct,
            min_value=None if row[3] is None else str(row[3]),
            max_value=None if row[4] is None else str(row[4]),
            mean=mean,
            std=std,
            top_values=top_values
        )

    def __init__(self, url: str):
        super().__init__(url)

        if psycopg is None: raise SystemExit("Не найден драйвер psycopg. Установите: pip install 'stats[postgres]'")

        try:
            # autocommit: a failed query does not break the next ones
            self.__connection = psycopg.connect(url, autocommit=True)
            self.__connection.execute(READ_ONLY)
        except psycopg.Error as err:
            raise SystemExit(f"Не удалось подключиться к базе: {err}")

    def list_tables(self, schema: str) -> list[str]:
        rows = self.__fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
            (schema,)
        )
        return [row[0] for row in rows]

    def table_row_count(self, table: str, schema: str) -> int:
        query = sql.SQL("SELECT COUNT(*) FROM {schema}.{table}").format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table)
        )
        return int(self.__fetch(query)[0][0])

    def column_metadata(self, table: str, schema: str) -> list[ColumnMeta]:
        rows = self.__fetch(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table)
        )
        return [
            ColumnMeta(
                name=name,
                data_type=TYPE_ALIASES.get(data_type, data_type),
                is_numeric=data_type in NUMERIC_TYPES,
                is_nullable=is_nullable == "YES"
            )
            for name, data_type, is_nullable in rows
        ]

    def column_aggregates(self, table: str, column: ColumnMeta, schema: str, limit: int | None = None, top: int = 5) -> ColumnAgg:
        source, params = self.__source(table, schema, limit)

        # one retry with text comparison for types that have no min/max or equality
        attempts = (False,) if column.is_numeric else (False, True)

        for as_text in attempts:
            try:
                return self.__aggregate(source, params, column, as_text, top)
            except psycopg.errors.UndefinedFunction:
                if as_text: raise

    def close(self) -> None:
        self.__connection.close()
