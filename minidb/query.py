"""Query execution engine for MiniDB."""

import functools
import re
from collections import defaultdict
from typing import Any

from .errors import InvalidQueryError, TableNotFoundError
from .parser import (
    Condition,
    CreateTableQuery,
    DeleteQuery,
    DropTableQuery,
    InsertQuery,
    OrderByItem,
    SelectColumn,
    SelectQuery,
    UpdateQuery,
    WhereClause,
)
from .planner import QueryPlanner, ScanType
from .table import Table
from .types import QueryResult, Row


class QueryExecutor:
    """Executes parsed SQL queries against the database."""

    def __init__(self, tables: dict[str, Table]):
        self.tables = tables

    def execute(self, query) -> QueryResult:
        """Execute a parsed query."""
        if isinstance(query, SelectQuery):
            return self.execute_select(query)
        elif isinstance(query, InsertQuery):
            return self.execute_insert(query)
        elif isinstance(query, UpdateQuery):
            return self.execute_update(query)
        elif isinstance(query, DeleteQuery):
            return self.execute_delete(query)
        elif isinstance(query, CreateTableQuery):
            self.execute_create_table(query)
            return None
        elif isinstance(query, DropTableQuery):
            self.execute_drop_table(query)
            return None
        else:
            raise InvalidQueryError(f'Unknown query type: {type(query)}')

    def execute_select(self, query: SelectQuery) -> list[Row]:
        """Execute a SELECT query."""
        # Get the main table
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        main_table = self.tables[query.table]

        # Get rows based on query plan (indexed rows with row IDs)
        if query.joins:
            indexed_rows = self._execute_join(main_table, query)
        else:
            indexed_rows = self._execute_table_scan(main_table, query)

        # Apply GROUP BY
        if query.group_by:
            result_rows = self._execute_group_by(indexed_rows, query)
        elif self._has_aggregates(query.columns):
            # Aggregate without GROUP BY - aggregate all rows
            result_rows = self._execute_aggregation(indexed_rows, query.columns)
        else:
            # Project columns
            result_rows = self._project_columns(indexed_rows, query.columns, query.table)

        # Apply ORDER BY
        if query.order_by:
            result_rows = self._execute_order_by(result_rows, query.order_by)

        # Apply LIMIT
        if query.limit is not None:
            result_rows = result_rows[: query.limit]

        return result_rows

    def _execute_table_scan(self, table: Table, query: SelectQuery) -> list[tuple[int, Row]]:
        """Execute a table scan with optional WHERE filtering."""
        planner = QueryPlanner(table)
        plan = planner.plan_select(query)

        rows = []

        if plan.scan_type == ScanType.INDEX_SCAN and plan.index_column is not None and query.where is not None:
            # Use index for equality lookup
            index = table.get_index(plan.index_column)
            condition = self._find_index_condition(query.where, plan.index_column)
            if condition:
                row_ids = index.lookup(condition.value)
                for row_id in row_ids:
                    row = table.get_row_by_id(row_id)
                    if row:
                        rows.append((row_id, row))
        elif plan.scan_type == ScanType.INDEX_RANGE_SCAN and plan.index_column is not None and query.where is not None:
            # Use index for range scan
            index = table.get_index(plan.index_column)
            condition = self._find_index_condition(query.where, plan.index_column)
            if condition:
                row_ids = index.range_lookup(condition.operator, condition.value)
                for row_id in row_ids:
                    row = table.get_row_by_id(row_id)
                    if row:
                        rows.append((row_id, row))
        else:
            # Full table scan
            for row_id, row in table.scan():
                if query.where and not self._evaluate_where(row, query.where):
                    continue
                rows.append((row_id, row))

        # Apply remaining WHERE conditions (for index scans)
        if query.where and plan.scan_type in (ScanType.INDEX_SCAN, ScanType.INDEX_RANGE_SCAN):
            rows = [(rid, row) for rid, row in rows if self._evaluate_where(row, query.where)]

        return rows

    def _execute_join(self, left_table: Table, query: SelectQuery) -> list[tuple[int, Row]]:
        """Execute a JOIN query."""

        # Get all rows from left table
        left_rows = list(left_table.scan())

        for join in query.joins:
            if join.table not in self.tables:
                raise TableNotFoundError(join.table)

            right_table = self.tables[join.table]
            right_rows = list(right_table.scan())

            # Build index on right table for join column
            right_index = defaultdict(list)
            for rid, row in right_rows:
                key = row.get(join.right_column)
                if key is not None:
                    right_index[key].append((rid, row))

            # Perform nested loop join
            new_rows = []
            for left_id, left_row in left_rows:
                left_key = left_row.get(join.left_column)
                matches = right_index.get(left_key, [])

                if matches:
                    for _right_id, right_row in matches:
                        # Merge rows with table prefixes
                        merged = {}
                        for col, val in left_row.items():
                            merged[col] = val
                            if query.table:
                                merged[f'{query.table}.{col}'] = val
                        for col, val in right_row.items():
                            if col not in merged:  # Don't overwrite left table columns
                                merged[col] = val
                            merged[f'{join.table}.{col}'] = val
                        new_rows.append((left_id, merged))
                elif join.join_type == 'LEFT':
                    # Left join: include left row with NULLs for right columns
                    merged = dict(left_row)
                    for col in right_table.columns:
                        merged[col] = None
                        merged[f'{join.table}.{col}'] = None
                    new_rows.append((left_id, merged))

            left_rows = new_rows

        # Apply WHERE clause
        if query.where:
            left_rows = [(rid, row) for rid, row in left_rows if self._evaluate_where(row, query.where)]

        return left_rows

    def _find_index_condition(self, where: WhereClause, column: str) -> Condition | None:
        """Find the condition that uses the index column."""
        if not where:
            return None

        for cond in where.conditions:
            if isinstance(cond, Condition) and cond.column == column:
                return cond

        return None

    def _evaluate_where(self, row: Row, where: WhereClause) -> bool:
        """Evaluate a WHERE clause against a row."""
        results = []

        for cond in where.conditions:
            if isinstance(cond, Condition):
                results.append(self._evaluate_condition(row, cond))
            elif isinstance(cond, WhereClause):
                results.append(self._evaluate_where(row, cond))

        if where.operator == 'AND':
            return all(results)
        else:  # OR
            return any(results)

    def _evaluate_condition(self, row: Row, condition: Condition) -> bool:
        """Evaluate a single condition against a row."""
        # Try with table prefix first
        col_name = condition.column
        if condition.table_alias:
            prefixed = f'{condition.table_alias}.{col_name}'
            if prefixed in row:
                col_name = prefixed

        if col_name not in row:
            return False

        value = row[col_name]
        cond_value = condition.value
        op = condition.operator

        if value is None:
            return False

        if op == '=':
            return value == cond_value
        elif op == '!=':
            return value != cond_value
        elif op == '>':
            return value > cond_value
        elif op == '>=':
            return value >= cond_value
        elif op == '<':
            return value < cond_value
        elif op == '<=':
            return value <= cond_value
        elif op == 'LIKE':
            return self._match_like(str(value), str(cond_value))
        elif op == 'IN':
            return value in cond_value

        return False

    def _match_like(self, value: str, pattern: str) -> bool:
        """Match a value against a LIKE pattern."""

        # Convert SQL LIKE pattern to regex
        # % matches any sequence, _ matches single character
        regex_pattern = '^'
        for char in pattern:
            if char == '%':
                regex_pattern += '.*'
            elif char == '_':
                regex_pattern += '.'
            else:
                regex_pattern += re.escape(char)
        regex_pattern += '$'

        return bool(re.match(regex_pattern, value, re.IGNORECASE))

    def _has_aggregates(self, columns: list[SelectColumn]) -> bool:
        """Check if any column has an aggregate function."""
        return any(col.aggregate for col in columns)

    def _execute_group_by(self, rows: list[tuple[int, Row]], query: SelectQuery) -> list[Row]:
        """Execute GROUP BY aggregation."""
        groups = defaultdict(list)

        for _row_id, row in rows:
            key = tuple(row.get(col) for col in query.group_by)
            groups[key].append(row)

        results = []
        for key, group_rows in groups.items():
            result_row = {}

            # Add group by columns
            for i, group_col in enumerate(query.group_by):
                result_row[group_col] = key[i]

            # Add aggregate columns
            for sel_col in query.columns:
                if sel_col.aggregate:
                    agg_value = self._compute_aggregate(
                        sel_col.aggregate.function, sel_col.aggregate.column, group_rows
                    )
                    agg_name = sel_col.alias or f'{sel_col.aggregate.function}({sel_col.aggregate.column})'
                    result_row[agg_name] = agg_value
                elif sel_col.name not in result_row and sel_col.name != '*':
                    result_row[sel_col.name] = group_rows[0].get(sel_col.name)

            results.append(result_row)

        return results

    def _execute_aggregation(self, rows: list[tuple[int, Row]], columns: list[SelectColumn]) -> list[Row]:
        """Execute aggregation without GROUP BY."""
        row_list = [row for _, row in rows]
        result_row = {}

        for col in columns:
            if col.aggregate:
                agg_value = self._compute_aggregate(col.aggregate.function, col.aggregate.column, row_list)
                agg_name = col.alias or f'{col.aggregate.function}({col.aggregate.column})'
                result_row[agg_name] = agg_value

        return [result_row] if result_row else []

    def _compute_aggregate(self, func: str, column: str, rows: list[Row]) -> Any:
        """Compute an aggregate function value."""
        if func == 'COUNT':
            if column == '*':
                return len(rows)
            return sum(1 for row in rows if row.get(column) is not None)

        values: list[Any] = [v for row in rows if (v := row.get(column)) is not None]

        if not values:
            return None

        if func == 'SUM':
            return sum(values)
        elif func == 'AVG':
            return sum(values) / len(values)
        elif func == 'MIN':
            return min(values)
        elif func == 'MAX':
            return max(values)

        return None

    def _project_columns(
        self, rows: list[tuple[int, Row]], columns: list[SelectColumn], table_name: str | None = None
    ) -> list[Row]:
        """Project selected columns from rows."""
        results = []

        for _row_id, row in rows:
            result = {}

            for col in columns:
                if col.name == '*':
                    # Select all columns
                    for key, val in row.items():
                        # Skip prefixed column names for clean output
                        if '.' not in key:
                            result[key] = val
                elif col.aggregate:
                    # Aggregates handled separately
                    pass
                else:
                    # Get column value
                    col_name = col.name
                    if col.table_alias:
                        prefixed = f'{col.table_alias}.{col_name}'
                        if prefixed in row:
                            result[col_name] = row[prefixed]
                            continue

                    if col_name in row:
                        result[col_name] = row[col_name]

            results.append(result)

        return results

    def _execute_order_by(self, rows: list[Row], order_by: list[OrderByItem]) -> list[Row]:
        """Sort rows by ORDER BY columns with per-column direction."""

        def _compare_rows(a: Row, b: Row) -> int:
            for item in order_by:
                col_name = item.column
                if item.table_alias:
                    col_name = f'{item.table_alias}.{item.column}'

                val_a = a.get(col_name, a.get(item.column))
                val_b = b.get(col_name, b.get(item.column))

                # NULLs sort last regardless of direction
                if val_a is None and val_b is None:
                    continue
                if val_a is None:
                    return 1
                if val_b is None:
                    return -1

                # Compare values
                if val_a < val_b:
                    cmp = -1
                elif val_a > val_b:
                    cmp = 1
                else:
                    continue

                # Reverse for DESC
                if item.direction == 'DESC':
                    cmp = -cmp

                return cmp

            return 0

        return sorted(rows, key=functools.cmp_to_key(_compare_rows))

    def execute_insert(self, query: InsertQuery) -> int:
        """Execute an INSERT query."""
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        table = self.tables[query.table]

        # Build row from columns and values
        row = dict(zip(query.columns, query.values, strict=False))

        row_id = table.insert(row)
        return row_id

    def execute_update(self, query: UpdateQuery) -> int:
        """Execute an UPDATE query."""
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        table = self.tables[query.table]

        # Find matching rows
        row_ids = set()
        for row_id, row in table.scan():
            if query.where and not self._evaluate_where(row, query.where):
                continue
            row_ids.add(row_id)

        # Update rows
        return table.update_rows(row_ids, query.set_clause)

    def execute_delete(self, query: DeleteQuery) -> int:
        """Execute a DELETE query."""
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        table = self.tables[query.table]

        # Find matching rows
        row_ids = set()
        for row_id, row in table.scan():
            if query.where and not self._evaluate_where(row, query.where):
                continue
            row_ids.add(row_id)

        # Delete rows
        return table.delete_rows(row_ids)

    def execute_create_table(self, query: CreateTableQuery) -> None:
        """Execute a CREATE TABLE query."""
        # This is handled by the Database class
        raise InvalidQueryError('CREATE TABLE should be handled by Database')

    def execute_drop_table(self, query: DropTableQuery) -> None:
        """Execute a DROP TABLE query."""
        # This is handled by the Database class
        raise InvalidQueryError('DROP TABLE should be handled by Database')
