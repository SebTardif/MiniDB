"""Query execution engine for MiniDB."""

import functools
import re
from collections import defaultdict
from typing import Any

from .errors import ColumnNotFoundError, InvalidQueryError, TableNotFoundError, TypeMismatchError
from .parser import (
    Condition,
    CreateTableQuery,
    DeleteQuery,
    DropTableQuery,
    InsertQuery,
    JoinClause,
    OrderByItem,
    SelectColumn,
    SelectQuery,
    UpdateQuery,
    WhereClause,
)
from .planner import QueryPlanner, ScanType
from .table import Table
from .types import QueryResult, Row


def _assign_output(
    result: dict[str, Any],
    written: dict[str, str | None],
    out_name: str,
    value: Any,
    qualifier: str | None,
) -> None:
    """Store a projected value. A second column with the same bare name gets a qualifier."""
    if out_name not in result:
        result[out_name] = value
        written[out_name] = qualifier
        return
    previous = written.get(out_name)
    if previous == qualifier:
        result[out_name] = value
        return
    if previous:
        result[f'{previous}.{out_name}'] = result.pop(out_name)
        written.pop(out_name, None)
    if qualifier:
        result[f'{qualifier}.{out_name}'] = value
    else:
        result[out_name] = value
        written[out_name] = None


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
        known_tables = self._known_tables(query)
        for join in query.joins:
            if join.table not in self.tables:
                raise TableNotFoundError(join.table)
        self._reject_unknown_query_columns(query, known_tables)

        # Get rows based on query plan (indexed rows with row IDs)
        if query.joins:
            indexed_rows = self._execute_join(main_table, query)
        else:
            indexed_rows = self._execute_table_scan(main_table, query)

        # Apply GROUP BY
        ordered_source = False
        if query.group_by:
            result_rows = self._execute_group_by(indexed_rows, query)
        elif self._has_aggregates(query.columns):
            # Aggregate without GROUP BY - aggregate all rows
            result_rows = self._execute_aggregation(indexed_rows, query)
        else:
            # Sort source rows first so ORDER BY can name a column that
            # the SELECT list does not return.
            if query.order_by:
                if query.distinct:
                    self._reject_distinct_order_by(query)
                indexed_rows = self._sort_indexed_rows(indexed_rows, query, known_tables)
                ordered_source = True
            result_rows = self._project_columns(indexed_rows, query.columns, query.table, known_tables)

        if query.having:
            if not query.group_by and not self._has_aggregates(query.columns):
                raise InvalidQueryError('HAVING requires GROUP BY or aggregate functions')
            result_rows = [row for row in result_rows if self._evaluate_where(row, query.having, known_tables)]

        if query.distinct:
            result_rows = self._deduplicate_rows(result_rows)

        # Grouped rows still carry the group key and the alias. Plain
        # selects were already ordered from the source rows.
        if query.order_by and not ordered_source:
            result_rows = self._execute_order_by(result_rows, query.order_by, known_tables)

        if query.group_by or query.having or self._has_aggregates(query.columns):
            keep = self._selected_output_keys(query)
            result_rows = [{key: value for key, value in row.items() if key in keep} for row in result_rows]

        # Apply LIMIT. A negative slice would drop rows from the end.
        if query.limit is not None:
            if query.limit < 0:
                raise InvalidQueryError('LIMIT must be zero or positive')
            result_rows = result_rows[: query.limit]

        return result_rows

    def _execute_table_scan(self, table: Table, query: SelectQuery) -> list[tuple[int, Row]]:
        """Execute a table scan with optional WHERE filtering."""
        planner = QueryPlanner(table)
        plan = planner.plan_select(query)
        known_tables = self._known_tables(query)
        rows: list[tuple[int, Row]] = []
        used_index = False

        # Only an operator this scan can apply may probe the index.
        # A leading LIKE, IN, or != must not hide a later comparison.
        if plan.scan_type == ScanType.INDEX_SCAN and plan.index_column is not None and query.where is not None:
            index = table.get_index(plan.index_column)
            condition = self._find_index_condition(query.where, plan.index_column, ('=',))
            if index is not None and condition is not None:
                used_index = True
                rows.extend(table.rows_for_ids(index.lookup(condition.value)))
        elif plan.scan_type == ScanType.INDEX_RANGE_SCAN and plan.index_column is not None and query.where is not None:
            index = table.get_index(plan.index_column)
            condition = self._find_index_condition(query.where, plan.index_column, ('<', '<=', '>', '>='))
            if index is not None and condition is not None:
                used_index = True
                rows.extend(table.rows_for_ids(index.range_lookup(condition.operator, condition.value)))

        if not used_index:
            for row_id, row in table.scan():
                if query.where and not self._evaluate_where(row, query.where, known_tables):
                    continue
                rows.append((row_id, row))
        elif query.where:
            rows = [(rid, row) for rid, row in rows if self._evaluate_where(row, query.where, known_tables)]

        return rows

    def _execute_join(self, left_table: Table, query: SelectQuery) -> list[tuple[int, Row]]:
        """Execute a JOIN query.

        Each new table joins to every table already in the FROM list.
        ON b.id still names b after a later table is joined.
        """
        left_rows = []
        for row_id, row in left_table.scan():
            merged = dict(row)
            if query.table:
                for col, val in row.items():
                    merged[f'{query.table}.{col}'] = val
            left_rows.append((row_id, merged))

        seen = [query.table]
        for join in query.joins:
            if join.join_type == 'RIGHT':
                raise InvalidQueryError('RIGHT JOIN is not supported; swap the tables and use LEFT JOIN')
            if join.table not in self.tables:
                raise TableNotFoundError(join.table)

            right_table = self.tables[join.table]
            left_spec, right_column = self._resolve_join_pair(seen, join, right_table)
            right_index: dict[Any, list[tuple[int, Row]]] = defaultdict(list)
            for rid, row in right_table.scan():
                key = row.get(right_column)
                if key is not None:
                    right_index[key].append((rid, row))

            new_rows = []
            for left_id, left_row in left_rows:
                left_key = self._join_left_value(left_row, left_spec)
                matches = right_index.get(left_key, []) if left_key is not None else []
                if matches:
                    for _right_id, right_row in matches:
                        merged = dict(left_row)
                        for col, val in right_row.items():
                            if col not in merged:
                                merged[col] = val
                            merged[f'{join.table}.{col}'] = val
                        new_rows.append((left_id, merged))
                elif join.join_type == 'LEFT':
                    merged = dict(left_row)
                    for col in right_table.columns:
                        if col not in merged:
                            merged[col] = None
                        merged[f'{join.table}.{col}'] = None
                    new_rows.append((left_id, merged))
            seen.append(join.table)
            left_rows = new_rows

        if query.where:
            known_tables = self._known_tables(query)
            left_rows = [(rid, row) for rid, row in left_rows if self._evaluate_where(row, query.where, known_tables)]
        return left_rows

    def _resolve_join_pair(
        self,
        seen: list[str],
        join: JoinClause,
        right_table: Table,
    ) -> tuple[tuple[str, str], str]:
        """Return ((previous table, column), right-table column) for ON."""

        def classify(qualifier: str | None, column: str) -> tuple[str, str, str]:
            if qualifier is None:
                return ('bare', '', column)
            if qualifier == join.table:
                if not right_table.schema.has_column(column):
                    raise ColumnNotFoundError(column, join.table)
                return ('right', qualifier, column)
            if qualifier in seen:
                table = self.tables.get(qualifier)
                if table is None or not table.schema.has_column(column):
                    raise ColumnNotFoundError(column, qualifier)
                return ('left', qualifier, column)
            raise InvalidQueryError(f"unknown table qualifier '{qualifier}'")

        def resolve_bare(column: str) -> tuple[str, str, str]:
            on_right = right_table.schema.has_column(column)
            owners = [name for name in seen if name in self.tables and self.tables[name].schema.has_column(column)]
            if on_right and owners:
                raise InvalidQueryError(f"Column '{column}' is ambiguous")
            if len(owners) > 1:
                raise InvalidQueryError(f"Column '{column}' is ambiguous")
            if on_right:
                return ('right', join.table, column)
            if len(owners) == 1:
                return ('left', owners[0], column)
            raise ColumnNotFoundError(column, join.table)

        # Unqualified ON keeps operand order: first column is already joined,
        # second column is the new table. `ON id = user_id` is users.id even
        # when the new table also has id.
        if join.left_table is None and join.right_table is None:
            owners = [
                name for name in seen if name in self.tables and self.tables[name].schema.has_column(join.left_column)
            ]
            if len(owners) != 1:
                raise InvalidQueryError(f"Column '{join.left_column}' is ambiguous")
            if not right_table.schema.has_column(join.right_column):
                raise ColumnNotFoundError(join.right_column, join.table)
            return (owners[0], join.left_column), join.right_column

        sides = []
        for qualifier, column in (
            (join.left_table, join.left_column),
            (join.right_table, join.right_column),
        ):
            kind, table, name = classify(qualifier, column)
            if kind == 'bare':
                kind, table, name = resolve_bare(name)
            sides.append((kind, table, name))

        lefts = [side for side in sides if side[0] == 'left']
        rights = [side for side in sides if side[0] == 'right']
        if len(lefts) != 1 or len(rights) != 1:
            raise InvalidQueryError(f'JOIN {join.table} must compare that table to a table already in the FROM clause')
        return (lefts[0][1], lefts[0][2]), rights[0][2]

    def _join_left_value(self, row: Row, spec: tuple[str, str]) -> Any:
        """Read the already-joined side of an ON predicate."""
        table, column = spec
        prefixed = f'{table}.{column}'
        if prefixed in row:
            return row[prefixed]
        return row.get(column)

    def _known_tables(self, query: SelectQuery) -> set[str]:
        """Table names this SELECT can qualify."""
        names = {query.table}
        for join in query.joins:
            names.add(join.table)
        return names

    def _find_index_condition(self, where: WhereClause, column: str, operators: tuple[str, ...]) -> Condition | None:
        """Find a top-level predicate on column whose operator this scan can apply.

        Nested OR arms are not probes. The planner only indexes a top-level
        AND conjunct, and the first nested equality is a different predicate.
        """
        if not where:
            return None

        for cond in where.conditions:
            if (
                isinstance(cond, Condition)
                and cond.column == column
                and not cond.negated
                and cond.operator in operators
            ):
                return cond

        return None

    def _require_column(
        self,
        column: str,
        table_alias: str | None,
        known_tables: set[str],
        fallback_table: str,
    ) -> None:
        """Raise when a qualifier or bare name is not a column of this query."""
        if table_alias:
            if table_alias not in known_tables:
                raise ColumnNotFoundError(column, table_alias)
            table = self.tables.get(table_alias)
            if table is None or not table.schema.has_column(column):
                raise ColumnNotFoundError(column, table_alias)
            return
        if not any(self.tables[name].schema.has_column(column) for name in known_tables if name in self.tables):
            raise ColumnNotFoundError(column, fallback_table)

    def _reject_unknown_where(self, where: WhereClause | None, known_tables: set[str], fallback_table: str) -> None:
        """Name check for WHERE. An empty index hit must not hide a bad column."""
        if where is None:
            return
        for cond in where.conditions:
            if isinstance(cond, WhereClause):
                self._reject_unknown_where(cond, known_tables, fallback_table)
            elif isinstance(cond, Condition):
                self._require_column(cond.column, cond.table_alias, known_tables, fallback_table)

    def _reject_unknown_query_columns(self, query: SelectQuery, known_tables: set[str]) -> None:
        """Reject unknown SELECT, WHERE, and qualified ORDER BY names before scanning."""
        for col in query.columns:
            if col.aggregate or col.name == '*':
                continue
            self._require_column(col.name, col.table_alias, known_tables, query.table)
        self._reject_unknown_where(query.where, known_tables, query.table)
        for item in query.order_by:
            if item.table_alias:
                self._require_column(item.column, item.table_alias, known_tables, query.table)

    def _read_qualified_column(
        self,
        row: Row,
        column: str,
        table_alias: str | None,
        known_tables: set[str] | None,
    ) -> Any:
        """Read a source-row column.

        A qualifier that is not a table in this query, or a column that
        table does not have, is missing even when the bare name exists.
        A real qualifier on an unprefixed single-table row still reads
        the bare value.
        """
        if table_alias:
            if known_tables is not None and (
                table_alias not in known_tables
                or table_alias not in self.tables
                or not self.tables[table_alias].schema.has_column(column)
            ):
                raise ColumnNotFoundError(column, table_alias)
            prefixed = f'{table_alias}.{column}'
            if prefixed in row:
                return row[prefixed]
            if any('.' in key for key in row):
                raise ColumnNotFoundError(column, table_alias)
        if column not in row:
            raise ColumnNotFoundError(column, table_alias)
        return row[column]

    def _evaluate_where(self, row: Row, where: WhereClause, known_tables: set[str] | None = None) -> bool:
        """Evaluate a WHERE clause against a row."""
        results = []

        for cond in where.conditions:
            if isinstance(cond, Condition):
                results.append(self._evaluate_condition(row, cond, known_tables))
            elif isinstance(cond, WhereClause):
                results.append(self._evaluate_where(row, cond, known_tables))

        if where.operator == 'AND':
            return all(results)
        else:  # OR
            return any(results)

    def _evaluate_condition(self, row: Row, condition: Condition, known_tables: set[str] | None = None) -> bool:
        """Evaluate a single condition against a row."""
        value = self._read_qualified_column(row, condition.column, condition.table_alias, known_tables)
        cond_value = condition.value
        op = condition.operator

        if op == 'IS NULL':
            result = value is None
        elif op == 'IS NOT NULL':
            result = value is not None
        elif value is None:
            return False
        elif op in ('=', '!=', '>', '>=', '<', '<='):
            self._reject_mismatched_compare(condition.column, value, cond_value)
            if op == '=':
                result = value == cond_value
            elif op == '!=':
                result = value != cond_value
            else:
                try:
                    if op == '>':
                        result = value > cond_value
                    elif op == '>=':
                        result = value >= cond_value
                    elif op == '<':
                        result = value < cond_value
                    else:
                        result = value <= cond_value
                except TypeError as exc:
                    raise TypeMismatchError(condition.column, type(value).__name__, type(cond_value).__name__) from exc
        elif op == 'LIKE':
            result = self._match_like(str(value), str(cond_value))
        elif op == 'IN':
            # NULL in the list makes the comparison unknown. WHERE drops unknown,
            # including NOT IN, instead of using Python membership.
            if isinstance(cond_value, (list, tuple)) and any(item is None for item in cond_value):
                if any(item is not None and value == item for item in cond_value):
                    result = True
                else:
                    return False
            else:
                for item in cond_value:
                    if item is not None:
                        self._reject_mismatched_compare(condition.column, value, item)
                result = value in cond_value
        else:
            return False

        if condition.negated:
            return not result
        return result

    def _reject_mismatched_compare(self, column: str, left: Any, right: Any) -> None:
        """Reject comparisons that Python would answer with a different type's rules.

        True compares equal to 1. A boolean predicate must not match an integer
        primary key, and an integer must not match a boolean column.
        """
        if isinstance(left, bool) or isinstance(right, bool):
            if isinstance(left, bool) and isinstance(right, bool):
                return
            raise TypeMismatchError(column, type(left).__name__, type(right).__name__)

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

        # LIKE stays case-insensitive. Equality stays case-sensitive.
        return bool(re.match(regex_pattern, value, re.IGNORECASE))

    def _deduplicate_rows(self, rows: list[Row]) -> list[Row]:
        """Drop duplicate projected rows, keeping first-seen order."""
        seen: set[tuple] = set()
        unique: list[Row] = []
        for row in rows:
            key = tuple(row.items())
            if key not in seen:
                seen.add(key)
                unique.append(row)
        return unique

    def _has_aggregates(self, columns: list[SelectColumn]) -> bool:
        """Check if any column has an aggregate function."""
        return any(col.aggregate for col in columns)

    def _column_in_query_schema(self, column: str, query: SelectQuery) -> bool:
        """Return True if column exists on the FROM table or any JOIN table."""
        main = self.tables.get(query.table)
        if main is not None and main.schema.has_column(column):
            return True
        for join in query.joins:
            joined = self.tables.get(join.table)
            if joined is not None and joined.schema.has_column(column):
                return True
        return False

    def _column_owner_count(self, column: str, known: set[str]) -> int:
        return sum(1 for name in known if name in self.tables and self.tables[name].schema.has_column(column))

    def _require_group_column(self, spec: str, known: set[str], query: SelectQuery) -> None:
        if '.' in spec:
            table, column = spec.split('.', 1)
            self._require_column(column, table, known, query.table)
            return
        if self._column_owner_count(spec, known) > 1:
            raise InvalidQueryError(f"Column '{spec}' is ambiguous")
        if not self._column_in_query_schema(spec, query):
            raise ColumnNotFoundError(spec, query.table)

    def _group_value(self, row: Row, spec: str, known: set[str]) -> Any:
        if '.' in spec:
            table, column = spec.split('.', 1)
            return self._read_qualified_column(row, column, table, known)
        owners = [name for name in known if name in self.tables and self.tables[name].schema.has_column(spec)]
        if len(owners) == 1:
            prefixed = f'{owners[0]}.{spec}'
            if prefixed in row:
                return row[prefixed]
        return row.get(spec)

    def _aggregate_label(self, col: SelectColumn) -> str:
        if col.alias:
            return col.alias
        assert col.aggregate is not None
        argument = col.aggregate.column
        if col.table_alias:
            argument = f'{col.table_alias}.{argument}'
        return f'{col.aggregate.function}({argument})'

    def _aggregate_cell(self, row: Row, column: str, table_alias: str | None, known: set[str]) -> Any:
        if table_alias:
            return self._read_qualified_column(row, column, table_alias, known)
        owners = [name for name in known if name in self.tables and self.tables[name].schema.has_column(column)]
        if len(owners) == 1:
            prefixed = f'{owners[0]}.{column}'
            if prefixed in row:
                return row[prefixed]
        return row.get(column)

    def _bare_name_is_grouped(self, name: str, group_by: list[str]) -> bool:
        for spec in group_by:
            column = spec.split('.', 1)[1] if '.' in spec else spec
            if column == name:
                return True
        return False

    def _select_is_grouped(self, sel: SelectColumn, group_by: list[str]) -> bool:
        for spec in group_by:
            if '.' in spec:
                table, column = spec.split('.', 1)
                if sel.name == column and (sel.table_alias is None or sel.table_alias == table):
                    return True
            elif sel.name == spec:
                return True
        return False

    def _grouped_select_value(self, row: Row, sel: SelectColumn, group_by: list[str], known: set[str]) -> Any:
        for spec in group_by:
            if '.' in spec:
                table, column = spec.split('.', 1)
                if sel.name == column and (sel.table_alias is None or sel.table_alias == table):
                    return self._read_qualified_column(row, column, table, known)
            elif sel.name == spec:
                return self._group_value(row, spec, known)
        return row.get(sel.name)

    def _execute_group_by(self, rows: list[tuple[int, Row]], query: SelectQuery) -> list[Row]:
        """Execute GROUP BY aggregation."""
        known = self._known_tables(query)
        for spec in query.group_by:
            self._require_group_column(spec, known, query)

        groups = defaultdict(list)

        for _row_id, row in rows:
            key = tuple(self._group_value(row, spec, known) for spec in query.group_by)
            groups[key].append(row)

        results = []
        for key, group_rows in groups.items():
            result_row = {}

            # Add group by columns
            for i, group_col in enumerate(query.group_by):
                result_row[group_col] = key[i]

            # Add selected columns. A bare column or * that is not grouped
            # would otherwise keep one arbitrary value and hide the rest.
            sample = group_rows[0]
            for sel_col in query.columns:
                if sel_col.aggregate:
                    agg_value = self._compute_aggregate(
                        sel_col.aggregate.function,
                        sel_col.aggregate.column,
                        group_rows,
                        query,
                        sel_col.table_alias,
                    )
                    agg_name = self._aggregate_label(sel_col)
                    if sel_col.alias and agg_name in result_row:
                        raise InvalidQueryError(f"Duplicate column name '{sel_col.alias}'")
                    result_row[agg_name] = agg_value
                elif sel_col.name == '*':
                    hidden = [
                        key for key in sample if '.' not in key and not self._bare_name_is_grouped(key, query.group_by)
                    ]
                    if hidden:
                        raise InvalidQueryError(f'SELECT * with GROUP BY leaves {hidden[0]!r} ungrouped')
                    continue
                elif not self._select_is_grouped(sel_col, query.group_by):
                    if sel_col.table_alias is None and self._column_owner_count(sel_col.name, known) > 1:
                        raise InvalidQueryError(f"Column '{sel_col.name}' is ambiguous")
                    raise InvalidQueryError(f"Column '{sel_col.name}' must appear in GROUP BY or be aggregated")
                else:
                    value = self._grouped_select_value(sample, sel_col, query.group_by, known)
                    out_name = sel_col.alias or sel_col.name
                    if sel_col.alias and out_name in result_row:
                        raise InvalidQueryError(f"Duplicate column name '{sel_col.alias}'")
                    result_row[out_name] = value

            for spec in self._having_aggregate_names(query.having):
                if spec not in result_row:
                    func, column = self._split_aggregate_spec(spec)
                    result_row[spec] = self._compute_aggregate(func, column, group_rows, query)

            results.append(result_row)

        return results

    def _having_aggregate_names(self, having: WhereClause | None) -> list[str]:
        """Collect FUNC(col) names referenced by HAVING."""
        if having is None:
            return []
        names: list[str] = []
        for cond in having.conditions:
            if isinstance(cond, Condition):
                if '(' in cond.column and cond.column.endswith(')'):
                    names.append(cond.column)
            elif isinstance(cond, WhereClause):
                names.extend(self._having_aggregate_names(cond))
        return names

    def _split_aggregate_spec(self, spec: str) -> tuple[str, str]:
        """Split 'COUNT(*)' or 'SUM(quantity)' into (function, column)."""
        func, rest = spec.split('(', 1)
        return func, rest[:-1]

    def _selected_output_keys(self, query: SelectQuery) -> set[str]:
        """Keys that belong in the user-visible SELECT output."""
        alias_for: dict[str, str] = {}
        for col in query.columns:
            if col.alias and not col.aggregate and col.name != '*':
                alias_for[col.name] = col.alias
        keys: set[str] = set()
        for name in query.group_by:
            if '.' not in name:
                keys.add(alias_for.get(name, name))
                continue
            table, column = name.split('.', 1)
            shown = any(
                col.name == column and (col.table_alias is None or col.table_alias == table)
                for col in query.columns
                if col.aggregate is None and col.name != '*'
            )
            if not shown:
                keys.add(name)
        for col in query.columns:
            if col.aggregate:
                keys.add(self._aggregate_label(col))
            elif col.name != '*':
                keys.add(col.alias or col.name)
        return keys

    def _execute_aggregation(self, rows: list[tuple[int, Row]], query: SelectQuery) -> list[Row]:
        """Execute aggregation without GROUP BY."""
        bare = [col.name for col in query.columns if not col.aggregate and col.name != '*']
        if bare:
            raise InvalidQueryError(f"Column '{bare[0]}' must appear in GROUP BY or be aggregated")
        if any(col.name == '*' and not col.aggregate for col in query.columns):
            raise InvalidQueryError('SELECT * cannot be combined with aggregates without GROUP BY')

        row_list = [row for _, row in rows]
        result_row = {}

        for col in query.columns:
            if col.aggregate:
                agg_value = self._compute_aggregate(
                    col.aggregate.function, col.aggregate.column, row_list, query, col.table_alias
                )
                agg_name = self._aggregate_label(col)
                if col.alias and agg_name in result_row:
                    raise InvalidQueryError(f"Duplicate column name '{col.alias}'")
                result_row[agg_name] = agg_value

        for spec in self._having_aggregate_names(query.having):
            if spec not in result_row:
                func, column = self._split_aggregate_spec(spec)
                result_row[spec] = self._compute_aggregate(func, column, row_list, query)

        return [result_row] if result_row else []

    def _compute_aggregate(
        self,
        func: str,
        column: str,
        rows: list[Row],
        query: SelectQuery,
        table_alias: str | None = None,
    ) -> Any:
        """Compute an aggregate function value."""
        known = self._known_tables(query)
        if table_alias is None and column not in ('*',) and '.' in column:
            table_alias, column = column.split('.', 1)
        if column != '*':
            if table_alias:
                self._require_column(column, table_alias, known, query.table)
            elif not self._column_in_query_schema(column, query):
                raise ColumnNotFoundError(column, query.table)
            elif self._column_owner_count(column, known) > 1:
                raise InvalidQueryError(f"Column '{column}' is ambiguous")

        def cell(row: Row) -> Any:
            return self._aggregate_cell(row, column, table_alias, known)

        if func == 'COUNT':
            if column == '*':
                return len(rows)
            return sum(1 for row in rows if cell(row) is not None)

        values: list[Any] = [v for row in rows if (v := cell(row)) is not None]

        if not values:
            return None

        try:
            if func == 'SUM':
                return sum(values)
            elif func == 'AVG':
                return sum(values) / len(values)
            elif func == 'MIN':
                return min(values)
            elif func == 'MAX':
                return max(values)
        except TypeError as exc:
            raise TypeMismatchError(column, 'number', type(values[0]).__name__) from exc

        return None

    def _project_columns(
        self,
        rows: list[tuple[int, Row]],
        columns: list[SelectColumn],
        table_name: str | None = None,
        known_tables: set[str] | None = None,
    ) -> list[Row]:
        """Project selected columns from rows."""
        results = []

        for _row_id, row in rows:
            result: dict[str, Any] = {}

            # Bare output name -> qualifier that produced it, if any.
            # Two tables both exposing `id` must not share one key.
            written: dict[str, str | None] = {}

            for col in columns:
                if col.name == '*':
                    if col.table_alias:
                        source = self.tables.get(col.table_alias)
                        if source is None:
                            raise ColumnNotFoundError('*', col.table_alias)
                        for schema_col in source.columns:
                            value = self._read_qualified_column(row, schema_col, col.table_alias, known_tables)
                            _assign_output(result, written, schema_col, value, col.table_alias)
                        continue
                    # Select all columns. Skip prefixed copies unless the
                    # bare name already belongs to the other table.
                    for key, val in row.items():
                        if '.' not in key:
                            _assign_output(result, written, key, val, None)
                    for key, val in row.items():
                        if '.' not in key:
                            continue
                        qualifier, bare = key.split('.', 1)
                        same_source = written.get(bare) in (None, qualifier)
                        if bare in result and (not same_source or result[bare] != val):
                            _assign_output(result, written, bare, val, qualifier)
                elif col.aggregate:
                    # Aggregates handled separately
                    pass
                else:
                    col_name = col.name
                    out_name = col.alias or col_name
                    if col.alias and out_name in result:
                        raise InvalidQueryError(f"Duplicate column name '{col.alias}'")
                    if col.table_alias:
                        value = self._read_qualified_column(row, col_name, col.table_alias, known_tables)
                        _assign_output(result, written, out_name, value, None if col.alias else col.table_alias)
                        continue

                    if col_name in row:
                        _assign_output(result, written, out_name, row[col_name], None)
                    else:
                        raise ColumnNotFoundError(col_name, table_name)

            results.append(result)

        return results

    def _reject_distinct_order_by(self, query: SelectQuery) -> None:
        """DISTINCT keeps one output row. A hidden sort key would pick which one."""
        if any(col.name == '*' and col.aggregate is None for col in query.columns):
            return
        visible: set[str] = set()
        for col in query.columns:
            if col.aggregate is not None:
                function = col.aggregate.function
                argument = col.aggregate.column
                visible.add(col.alias or f'{function}({argument})')
                continue
            visible.add(col.alias or col.name)
        for item in query.order_by:
            if item.column not in visible:
                raise InvalidQueryError(f'ORDER BY {item.column} must appear in the SELECT list when DISTINCT is used')

    def _sort_indexed_rows(
        self,
        rows: list[tuple[int, Row]],
        query: SelectQuery,
        known_tables: set[str],
    ) -> list[tuple[int, Row]]:
        """Order source rows, including columns the SELECT list omits."""
        views: list[Row] = []
        paired: list[tuple[Row, tuple[int, Row]]] = []
        for indexed in rows:
            _row_id, row = indexed
            view = dict(row)
            for col in query.columns:
                if col.alias is None or col.aggregate is not None or col.name == '*':
                    continue
                if col.table_alias:
                    view[col.alias] = self._read_qualified_column(row, col.name, col.table_alias, known_tables)
                elif col.name in row:
                    view[col.alias] = row[col.name]
            views.append(view)
            paired.append((view, indexed))
        ordered = self._execute_order_by(views, query.order_by, known_tables)
        by_identity = {id(view): indexed for view, indexed in paired}
        return [by_identity[id(view)] for view in ordered]

    def _execute_order_by(
        self,
        rows: list[Row],
        order_by: list[OrderByItem],
        known_tables: set[str] | None = None,
    ) -> list[Row]:
        """Sort rows by ORDER BY columns with per-column direction."""
        for item in order_by:
            if item.table_alias and known_tables is not None:
                self._require_column(item.column, item.table_alias, known_tables, item.table_alias)
        if rows:
            sample = rows[0]
            for item in order_by:
                if item.table_alias:
                    prefixed = f'{item.table_alias}.{item.column}'
                    if prefixed not in sample and item.column not in sample:
                        raise ColumnNotFoundError(item.column, item.table_alias)
                elif item.column not in sample:
                    raise ColumnNotFoundError(item.column)

        def _order_value(row: Row, item: OrderByItem) -> Any:
            if item.table_alias:
                prefixed = f'{item.table_alias}.{item.column}'
                if prefixed in row:
                    return row[prefixed]
            return row.get(item.column)

        def _compare_rows(a: Row, b: Row) -> int:
            for item in order_by:
                val_a = _order_value(a, item)
                val_b = _order_value(b, item)

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

        if len(query.columns) != len(query.values):
            raise InvalidQueryError(
                f'column count ({len(query.columns)}) does not match value count ({len(query.values)})'
            )

        for col in query.columns:
            if not table.schema.has_column(col):
                raise ColumnNotFoundError(col, query.table)

        seen_columns: set[str] = set()
        for col in query.columns:
            if col in seen_columns:
                raise InvalidQueryError(f"Duplicate column name '{col}'")
            seen_columns.add(col)

        row = dict(zip(query.columns, query.values, strict=True))

        row_id = table.insert(row)
        return row_id

    def execute_update(self, query: UpdateQuery) -> int:
        """Execute an UPDATE query."""
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        table = self.tables[query.table]

        validated_updates: dict[str, Any] = {}
        for col, value in query.set_clause.items():
            column = table.schema.get_column(col)
            if column is None:
                raise ColumnNotFoundError(col, query.table)
            validated_updates[col] = column.validate(value)

        # Find matching rows
        known_tables = {query.table}
        self._reject_unknown_where(query.where, known_tables, query.table)
        row_ids = set()
        for row_id, row in table.scan():
            if query.where and not self._evaluate_where(row, query.where, known_tables):
                continue
            row_ids.add(row_id)

        # Update rows
        return table.update_rows(row_ids, validated_updates)

    def execute_delete(self, query: DeleteQuery) -> int:
        """Execute a DELETE query."""
        if query.table not in self.tables:
            raise TableNotFoundError(query.table)

        table = self.tables[query.table]

        # Find matching rows
        known_tables = {query.table}
        self._reject_unknown_where(query.where, known_tables, query.table)
        row_ids = set()
        for row_id, row in table.scan():
            if query.where and not self._evaluate_where(row, query.where, known_tables):
                continue
            row_ids.add(row_id)

        # Delete rows
        return table.delete_rows(row_ids)

    def execute_create_table(self, query: CreateTableQuery) -> None:
        """Execute a CREATE TABLE query."""
        # This is handled by the Database class
        raise InvalidQueryError('CREATE TABLE should be handled by MiniDB.execute()')

    def execute_drop_table(self, query: DropTableQuery) -> None:
        """Execute a DROP TABLE query."""
        # This is handled by the Database class
        raise InvalidQueryError('DROP TABLE should be handled by MiniDB.execute()')
