"""Main database API for MiniDB."""

from .column import Column, Schema
from .errors import MiniDBError, TableExistsError, TableNotFoundError
from .parser import CreateTableQuery, DropTableQuery, parse_sql
from .persistence import load_database, save_database
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

    def execute(self, sql: str) -> QueryResult:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement string

        Returns:
            - For SELECT: list of row dictionaries
            - For INSERT: row ID (int)
            - For UPDATE/DELETE: number of affected rows (int)
            - For CREATE/DROP TABLE: None

        Raises:
            MiniDBError: If query execution fails
        """
        query = parse_sql(sql)

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

    def query(self, sql: str) -> list[Row]:
        """
        Execute a SELECT query and return results.

        Args:
            sql: SELECT statement

        Returns:
            List of row dictionaries

        Raises:
            MiniDBError: If query execution fails
        """
        result = self.execute(sql)
        if isinstance(result, list):
            return result
        raise MiniDBError('Query did not return rows')

    def save(self, filepath: str) -> None:
        """
        Save the database to a file.

        Args:
            filepath: Path to the output file
        """
        save_database(self, filepath)

    @classmethod
    def load(cls, filepath: str) -> 'MiniDB':
        """
        Load a database from a file.

        Args:
            filepath: Path to the input file

        Returns:
            Loaded database instance
        """
        return load_database(filepath)

    def __repr__(self) -> str:
        """String representation of the database."""
        table_info = ', '.join(f'{name}({len(table.rows)} rows)' for name, table in self._tables.items())
        return f'MiniDB({table_info})'

    def __len__(self) -> int:
        """Return number of tables."""
        return len(self._tables)

    def __contains__(self, table_name: str) -> bool:
        """Check if a table exists."""
        return table_name in self._tables
