"""
    Desc: Dialect class, a base for every supported database
    Creator: Kirosha
"""

from abc import ABC, abstractmethod

from stats.models import ColumnMeta, ColumnAgg

class Dialect(ABC):
    def __init__(self, url: str):
        self._url = url

    @abstractmethod
    def list_tables(self, schema: str) -> list[str]:
        """base tables of the schema, sorted by name"""

    @abstractmethod
    def table_row_count(self, table: str, schema: str) -> int:
        """exact row count of the whole table"""

    @abstractmethod
    def column_metadata(self, table: str, schema: str) -> list[ColumnMeta]:
        """columns of the table in their declared order"""

    @abstractmethod
    def column_aggregates(self, table: str, column: ColumnMeta, schema: str, limit: int | None = None, top: int = 5) -> ColumnAgg:
        """aggregates are counted on the database side, over the first `limit` rows if limit is set"""

    def close(self) -> None:
        pass
