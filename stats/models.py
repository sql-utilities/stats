"""
    Desc: Models to describe column(s), aggregate(s) and statistics
    Creator: Kirosha
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class ColumnMeta:
    name: str
    data_type: str
    is_numeric: bool
    is_nullable: bool

@dataclass(frozen=True)
class ColumnAgg:
    # all numbers are counted over the sample when the table is sampled
    count: int
    non_null: int
    distinct: int
    min_value: str | None
    max_value: str | None
    mean: float | None
    std: float | None
    top_values: list[tuple[str, int]]

@dataclass
class ColumnStats:
    meta: ColumnMeta
    agg: ColumnAgg

    @property
    def null_count(self) -> int:
        return self.agg.count - self.agg.non_null

    @property
    def null_pct(self) -> float:
        if not self.agg.count: return 0.0
        return self.null_count / self.agg.count * 100

@dataclass
class TableStats:
    name: str
    schema: str
    # row count of the whole table, even if the columns are sampled
    row_count: int
    sampled: bool
    sample_limit: int | None
    columns: list[ColumnStats]

    @property
    def column_count(self) -> int:
        return len(self.columns)
