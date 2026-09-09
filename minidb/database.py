"""Main database API for MiniDB."""

import copy
from collections.abc import Sequence
from typing import Any

from .column import Column, Schema
from .errors import InvalidQueryError, MiniDBError, TableExistsError, TableNotFoundError
from .parser import (
    BeginQuery,
    CommitQuery,
    CreateTableQuery,
    DropTableQuery,
    RollbackQuery,
    SelectQuery,
    bind_params,
    parse_sql,
)
from .persistence import _deserialize, _serialize
from .planner import QueryPlanner
from .query import QueryExecutor
from .table import Table
from .types import QueryResult, Row


class MiniDB:
    """
    MiniDB - A miniature in-memory database with SQL-like query support.

    Example usage:
        db = MiniDB()

        # Create a table
        db.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name STRING,
                age INTEGER,
                salary FLOAT,
                active BOOLEAN
            )
        ''')

        # Insert data
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")

        # Query data
        results = db.query("SELECT * FROM users WHERE age > 25")

        # Save to file
        db.save('database.json')

        # Load from file
        db = MiniDB.load('database.json')
    """

    def __init__(self):
        """Initialize an empty database."""
        self._tables: dict[str, Table] = {}
        self._executor: QueryExecutor | None = None
        self._txn_snapshot: dict[str, Table] | None = None

    @property
    def tables(self) -> list[str]:
        """Get list of table names."""
        return list(self._tables.keys())

    @property
    def executor(self) -> QueryExecutor:
        """Get or create the query executor."""
        if self._executor is None:
            self._executor = QueryExecutor(self._tables)
        return self._executor

    def create_table(self, name: str, columns: list[Column]) -> None:
        """
        Programmatically create a table.

        Args:
            name: Table name
            columns: List of Column objects

        Raises:
            TableExistsError: If table already exists
        """
        if name in self._tables:
            raise TableExistsError(name)

        schema = Schema(columns=columns)
        table = Table(name=name, schema=schema)
        self._tables[name] = table

        # Reset executor to pick up new tables
        self._executor = None

    def drop_table(self, name: str) -> None:
        """
        Drop a table.

        Args:
            name: Table name

        Raises:
            TableNotFoundError: If table doesn't exist
        """
        if name not in self._tables:
            raise TableNotFoundError(name)

        del self._tables[name]
        self._executor = None

    def get_table(self, name: str) -> Table | None:
        """Get a table by name."""
        return self._tables.get(name)

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> QueryResult:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement string
            params: Values for ? placeholders, bound left-to-right after parse

        Returns:
            - For SELECT: list of row dictionaries
            - For INSERT: row ID (int)
            - For UPDATE/DELETE: number of affected rows (int)
            - For CREATE/DROP TABLE: None
            - For BEGIN/COMMIT/ROLLBACK: None

        Raises:
            MiniDBError: If query execution fails
        """
        query = parse_sql(sql)
        bind_params(query, params)

        if isinstance(query, BeginQuery):
            if self._txn_snapshot is not None:
                raise InvalidQueryError('already in a transaction')
            self._txn_snapshot = {
                name: Table.from_dict(copy.deepcopy(table.to_dict())) for name, table in self._tables.items()
            }
            return None

        if isinstance(query, CommitQuery):
            if self._txn_snapshot is None:
                raise InvalidQueryError('no transaction in progress')
            self._txn_snapshot = None
            self._executor = None
            return None

        if isinstance(query, RollbackQuery):
            if self._txn_snapshot is None:
                raise InvalidQueryError('no transaction in progress')
            self._tables = self._txn_snapshot
            self._txn_snapshot = None
            self._executor = None
            return None

        if isinstance(query, CreateTableQuery):
            columns = [
                Column(name=col.name, type=col.type, primary_key=col.primary_key, nullable=col.nullable)
                for col in query.columns
            ]
            self.create_table(query.table, columns)
            return None

        elif isinstance(query, DropTableQuery):
            self.drop_table(query.table)
            return None

        else:
            return self.executor.execute(query)

    def query(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        """
        Execute a SELECT query and return results.

        Args:
            sql: SELECT statement
            params: Values for ? placeholders, bound left-to-right after parse

        Returns:
            List of row dictionaries

        Raises:
            MiniDBError: If the statement is not SELECT or execution fails
        """
        result = self.execute(sql, params)
        if isinstance(result, list):
            return result
        raise MiniDBError('query() only runs SELECT; use execute() for INSERT, UPDATE, DELETE, CREATE, or DROP')

    def explain(self, sql: str, params: Sequence[Any] | None = None) -> str:
        """
        Return the query plan for a SELECT statement.

        Args:
            sql: SELECT statement
            params: Values for ? placeholders, bound before planning

        Returns:
            String representation of the planned scan

        Raises:
            MiniDBError: If the statement is not SELECT
            TableNotFoundError: If the FROM table does not exist
        """
        query = parse_sql(sql)
        bind_params(query, params)
        if not isinstance(query, SelectQuery):
            raise MiniDBError('explain() is SELECT-only')
        if query.table not in self._tables:
            raise TableNotFoundError(query.table)
        return str(QueryPlanner(self._tables[query.table]).plan_select(query))

    def save(self, filepath: str) -> None:
        """
        Save the database to a file.

        Args:
            filepath: Path to the output file
        """
        _serialize(self._tables, filepath)

    @classmethod
    def load(cls, filepath: str) -> 'MiniDB':
        """
        Load a database from a file.

        Args:
            filepath: Path to the input file

        Returns:
            Loaded database instance
        """
        tables = _deserialize(filepath)
        db = cls()
        db._tables = tables
        return db

    def __repr__(self) -> str:
        """String representation of the database."""
        table_info = ', '.join(f'{name}({table.row_count} rows)' for name, table in self._tables.items())
        return f'MiniDB({table_info})'

    def __len__(self) -> int:
        """Return number of tables."""
        return len(self._tables)

    def __contains__(self, table_name: str) -> bool:
        """Check if a table exists."""
        return table_name in self._tables
