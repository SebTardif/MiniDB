"""
MiniDB - A miniature in-memory database with SQL-like query support.

Features:
- CREATE TABLE with typed columns (INTEGER, STRING, FLOAT, BOOLEAN)
- INSERT, SELECT, UPDATE, DELETE operations
- WHERE clause with AND/OR, comparisons (=, >, <, LIKE, IN)
- ORDER BY for sorting
- GROUP BY with aggregations (COUNT, SUM, AVG, MIN, MAX)
- JOIN between tables
- Automatic indexing on primary keys
- Query planner (index scan vs table scan)
- Persistence to JSON files

Example:
    from minidb import MiniDB, Column, ColumnType

    # Create database
    db = MiniDB()

    # Create table programmatically
    db.create_table('users', [
        Column('id', ColumnType.INTEGER, primary_key=True),
        Column('name', ColumnType.STRING),
        Column('age', ColumnType.INTEGER),
    ])

    # Or use SQL
    db.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            total FLOAT
        )
    ''')

    # Insert data
    db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO orders (id, user_id, total) VALUES (1, 1, 99.99)")

    # Query with SQL
    results = db.query('''
        SELECT users.name, orders.total
        FROM users
        JOIN orders ON users.id = orders.user_id
        WHERE users.age > 25
    ''')

    # Save and load
    db.save('mydb.json')
    db = MiniDB.load('mydb.json')
"""

from .column import Column, Schema
from .database import MiniDB
from .errors import (
    AmbiguousColumnError,
    ColumnError,
    ColumnExistsError,
    ColumnNotFoundError,
    ConstraintError,
    DuplicateKeyError,
    FileReadError,
    FileWriteError,
    InvalidQueryError,
    MiniDBError,
    NullValueError,
    ParseError,
    PersistenceError,
    PrimaryKeyError,
    QueryError,
    SyntaxError_,
    TableError,
    TableExistsError,
    TableNotFoundError,
    TypeError_,
    TypeMismatchError,
    VersionMismatchError,
)
from .index import HashIndex, IndexManager
from .parser import (
    CreateTableQuery,
    DeleteQuery,
    DropTableQuery,
    InsertQuery,
    Lexer,
    Parser,
    SelectQuery,
    Token,
    UpdateQuery,
    parse_sql,
)
from .persistence import _deserialize as load_database
from .persistence import _serialize as save_database
from .planner import QueryPlan, QueryPlanner, ScanType
from .query import QueryExecutor
from .table import Table
from .types import ColumnType, QueryResult, QueryType, Row, TokenType

__all__ = [
    'AmbiguousColumnError',
    # Schema
    'Column',
    'ColumnError',
    'ColumnExistsError',
    'ColumnNotFoundError',
    # Types
    'ColumnType',
    'ConstraintError',
    'CreateTableQuery',
    'DeleteQuery',
    'DropTableQuery',
    'DuplicateKeyError',
    'FileReadError',
    'FileWriteError',
    # Indexing
    'HashIndex',
    'IndexManager',
    'InsertQuery',
    'InvalidQueryError',
    'Lexer',
    # Main API
    'MiniDB',
    # Errors
    'MiniDBError',
    'NullValueError',
    'ParseError',
    'Parser',
    'PersistenceError',
    'PrimaryKeyError',
    'QueryError',
    # Query execution
    'QueryExecutor',
    'QueryPlan',
    # Query planning
    'QueryPlanner',
    'QueryResult',
    'QueryType',
    'Row',
    'ScanType',
    'Schema',
    'SelectQuery',
    'SyntaxError_',
    # Storage
    'Table',
    'TableError',
    'TableExistsError',
    'TableNotFoundError',
    'Token',
    'TokenType',
    'TypeError_',
    'TypeMismatchError',
    'UpdateQuery',
    'VersionMismatchError',
    'load_database',
    # Parsing
    'parse_sql',
    # Persistence
    'save_database',
]

__version__ = '1.0.2'
