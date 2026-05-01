"""Query planner for MiniDB."""

from dataclasses import dataclass
from enum import Enum

from .parser import Condition, SelectQuery, WhereClause
from .table import Table


class ScanType(Enum):
    """Types of table scans."""

    TABLE_SCAN = 'table_scan'
    INDEX_SCAN = 'index_scan'
    INDEX_RANGE_SCAN = 'index_range_scan'


@dataclass
class QueryPlan:
    """Represents a query execution plan."""

    scan_type: ScanType
    index_column: str | None = None
    estimated_rows: int = 0
    use_index_for: str | None = None  # The specific condition using index

    def __str__(self) -> str:
        if self.scan_type == ScanType.TABLE_SCAN:
            return f'QueryPlan(table_scan, estimated_rows={self.estimated_rows})'
        elif self.scan_type == ScanType.INDEX_SCAN:
            return f"QueryPlan(index_scan on '{self.index_column}', estimated_rows={self.estimated_rows})"
        else:
            return f"QueryPlan(index_range_scan on '{self.index_column}', estimated_rows={self.estimated_rows})"


class QueryPlanner:
    """
    Analyzes queries and determines the optimal execution strategy.

    Decides between:
    - Full table scan
    - Index lookup (equality)
    - Index range scan (comparisons)
    """

    def __init__(self, table: Table):
        self.table = table

    def plan_select(self, query: SelectQuery) -> QueryPlan:
        """
        Create an execution plan for a SELECT query.

        Args:
            query: The parsed SELECT query

        Returns:
            A QueryPlan with the chosen execution strategy
        """
        total_rows = self.table.row_count

        # No WHERE clause - must do table scan
        if not query.where:
            return QueryPlan(scan_type=ScanType.TABLE_SCAN, estimated_rows=total_rows)

        # Check if we can use an index
        index_condition = self._find_index_condition(query.where)

        if index_condition:
            column, operator, value = index_condition

            # Equality on indexed column - use index scan
            if operator == '=':
                # Estimate: usually 1 row for PK, but could be more
                estimated = self._estimate_equality_rows(column, value)
                return QueryPlan(
                    scan_type=ScanType.INDEX_SCAN,
                    index_column=column,
                    estimated_rows=estimated,
                    use_index_for=f'{column} = {value!r}',
                )

            # Range comparison - use index range scan
            elif operator in ('<', '<=', '>', '>='):
                estimated = self._estimate_range_rows(operator, value, total_rows)
                return QueryPlan(
                    scan_type=ScanType.INDEX_RANGE_SCAN,
                    index_column=column,
                    estimated_rows=estimated,
                    use_index_for=f'{column} {operator} {value!r}',
                )

        # No usable index - table scan
        return QueryPlan(scan_type=ScanType.TABLE_SCAN, estimated_rows=total_rows)

    def _find_index_condition(self, where: WhereClause) -> tuple | None:
        """
        Find a condition that can use an index.

        Returns:
            Tuple of (column, operator, value) or None
        """
        # For AND conditions, find first index-usable condition
        if where.operator == 'AND':
            for cond in where.conditions:
                result = self._check_condition_for_index(cond)
                if result:
                    return result
        # For OR conditions, all must use same index (rare)
        else:
            # For simplicity, don't use index for OR conditions
            pass

        return None

    def _check_condition_for_index(self, condition) -> tuple | None:
        """Check if a condition can use an index."""
        if isinstance(condition, Condition):
            column = condition.column
            operator = condition.operator
            value = condition.value

            # Check if column has an index
            if self.table.has_index(column) and operator in ('=', '<', '<=', '>', '>='):
                return (column, operator, value)

        return None

    def _estimate_equality_rows(self, column: str, value) -> int:
        """Estimate rows returned by an equality lookup."""
        index = self.table.get_index(column)
        if index:
            return len(index.lookup(value))
        return 1  # Assume unique for PK

    def _estimate_range_rows(self, op: str, value, total_rows: int) -> int:
        """
        Estimate rows returned by a range scan.

        Simple heuristic: assume uniform distribution.
        """
        # For simplicity, estimate 30% of rows for range queries
        # A real database would use statistics
        if op in ('<', '<='):
            return max(1, total_rows // 3)
        else:  # '>', '>='
            return max(1, total_rows // 3)

    def get_row_ids_for_condition(self, condition: Condition) -> set[int] | None:
        """
        Get row IDs that match a condition using an index.

        Returns None if index cannot be used.
        """
        column = condition.column
        operator = condition.operator
        value = condition.value

        if not self.table.has_index(column):
            return None

        index = self.table.get_index(column)

        if operator == '=':
            return index.lookup(value)
        elif operator in ('<', '<=', '>', '>='):
            return index.range_lookup(operator, value)

        return None
