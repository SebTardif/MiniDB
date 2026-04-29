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

from .types import ColumnType, TokenType, QueryType, Row, QueryResult
from .column import Column, Schema
from .table import Table
from .index import HashIndex, IndexManager
from .parser import (
    parse_sql,
    SelectQuery, InsertQuery, UpdateQuery, DeleteQuery,
    CreateTableQuery, DropTableQuery,
    Token, Lexer, Parser
)
from .planner import QueryPlanner, QueryPlan, ScanType
from .query import QueryExecutor
from .persistence import save_database, load_database
from .database import MiniDB
from .errors import (
    MiniDBError,
    TableError, TableNotFoundError, TableExistsError,
    ColumnError, ColumnNotFoundError, ColumnExistsError,
    TypeError_, TypeMismatchError, NullValueError,
    ParseError, SyntaxError_,
    QueryError, InvalidQueryError, AmbiguousColumnError,
    ConstraintError, PrimaryKeyError, DuplicateKeyError,
    PersistenceError, FileReadError, FileWriteError, VersionMismatchError,
)

__all__ = [
    # Main API
    'MiniDB',
    
    # Types
    'ColumnType',
    'TokenType',
    'QueryType',
    'Row',
    'QueryResult',
    
    # Schema
    'Column',
    'Schema',
    
    # Storage
    'Table',
    
    # Indexing
    'HashIndex',
    'IndexManager',
    
    # Parsing
    'parse_sql',
    'SelectQuery',
    'InsertQuery',
    'UpdateQuery',
    'DeleteQuery',
    'CreateTableQuery',
    'DropTableQuery',
    'Token',
    'Lexer',
    'Parser',
    
    # Query planning
    'QueryPlanner',
    'QueryPlan',
    'ScanType',
    
    # Query execution
    'QueryExecutor',
    
    # Persistence
    'save_database',
    'load_database',
    
    # Errors
    'MiniDBError',
    'TableError',
    'TableNotFoundError',
    'TableExistsError',
    'ColumnError',
    'ColumnNotFoundError',
    'ColumnExistsError',
    'TypeError_',
    'TypeMismatchError',
    'NullValueError',
    'ParseError',
    'SyntaxError_',
    'QueryError',
    'InvalidQueryError',
    'AmbiguousColumnError',
    'ConstraintError',
    'PrimaryKeyError',
    'DuplicateKeyError',
    'PersistenceError',
    'FileReadError',
    'FileWriteError',
    'VersionMismatchError',
]

__version__ = '1.0.0'
