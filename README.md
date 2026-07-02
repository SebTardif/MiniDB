# MiniDB

A miniature in-memory database with SQL-like query support, built from scratch using only Python 3.11+ standard library.

## Features

- **Typed Columns**: INTEGER, STRING, FLOAT, BOOLEAN
- **CRUD Operations**: INSERT, SELECT, UPDATE, DELETE
- **SQL-like Query Language**:
  - WHERE with AND/OR comparisons (=, >, <, >=, <=, !=, LIKE, IN)
  - ORDER BY (ASC/DESC)
  - GROUP BY with aggregations
  - LIMIT clause
- **Aggregations**: COUNT, SUM, AVG, MIN, MAX
- **JOINs**: INNER JOIN and LEFT JOIN between tables
- **Indexing**: Automatic hash-based indexing on primary keys
- **Query Planner**: Chooses between index scans and table scans
- **Persistence**: Save/load database to JSON files with versioning

## Installation

No installation required! MiniDB uses only Python standard library.

```bash
# Just clone and use
git clone https://github.com/SebTardif/MiniDB.git
cd MiniDB
python -m pytest tests/ -v  # Run tests
python main.py              # Run demo
```

## Quick Start

```python
from minidb import MiniDB, Column, ColumnType

# Create database
db = MiniDB()

# Create table using SQL
db.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name STRING,
        age INTEGER,
        salary FLOAT,
        active BOOLEAN
    )
''')

# Or create table programmatically
db.create_table('orders', [
    Column('id', ColumnType.INTEGER, primary_key=True),
    Column('user_id', ColumnType.INTEGER),
    Column('product', ColumnType.STRING),
    Column('total', ColumnType.FLOAT),
])

# Insert data
db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 75000.0, true)")
db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 55000.0, false)")

# Query data
results = db.query("SELECT * FROM users WHERE age > 28")

# Complex queries
results = db.query('''
    SELECT name, salary FROM users
    WHERE active = true AND salary > 60000
    ORDER BY salary DESC
''')

# Aggregations
results = db.query("SELECT COUNT(*), AVG(salary) FROM users")

# GROUP BY
results = db.query('''
    SELECT active, COUNT(*), AVG(salary)
    FROM users
    GROUP BY active
''')

# JOINs
results = db.query('''
    SELECT users.name, orders.product, orders.total
    FROM users
    JOIN orders ON users.id = orders.user_id
    WHERE orders.total > 50
''')

# UPDATE
affected = db.execute("UPDATE users SET salary = 80000.0 WHERE id = 1")

# DELETE
affected = db.execute("DELETE FROM users WHERE active = false")

# Persistence
db.save('my_database.json')
db = MiniDB.load('my_database.json')
```

## SQL Syntax Reference

### CREATE TABLE

```sql
CREATE TABLE table_name (
    column1 INTEGER PRIMARY KEY,
    column2 STRING,
    column3 FLOAT,
    column4 BOOLEAN
)
```

### INSERT

```sql
INSERT INTO table_name (col1, col2, col3) VALUES (1, 'value', 3.14)
```

### SELECT

```sql
SELECT * FROM table_name
SELECT col1, col2 FROM table_name
SELECT col1, COUNT(*), AVG(col2) FROM table_name GROUP BY col1
```

### WHERE Clause

```sql
WHERE col = value
WHERE col > value
WHERE col >= value
WHERE col < value
WHERE col <= value
WHERE col != value
WHERE col LIKE 'pattern%'     -- % matches any sequence
WHERE col IN (1, 2, 3)
WHERE cond1 AND cond2
WHERE cond1 OR cond2
```

### ORDER BY

```sql
ORDER BY col ASC
ORDER BY col DESC
ORDER BY col1 ASC, col2 DESC
```

### LIMIT

```sql
LIMIT 10
```

### JOIN

```sql
SELECT t1.col, t2.col
FROM t1
JOIN t2 ON t1.id = t2.t1_id

-- LEFT JOIN (includes unmatched left rows with NULLs)
SELECT t1.col, t2.col
FROM t1
LEFT JOIN t2 ON t1.id = t2.t1_id
```

### UPDATE

```sql
UPDATE table_name SET col1 = value1, col2 = value2 WHERE condition
```

### DELETE

```sql
DELETE FROM table_name WHERE condition
```

## Architecture

```
minidb/
├── __init__.py      # Public API exports
├── database.py      # MiniDB main class
├── table.py         # Table storage
├── column.py        # Column and Schema definitions
├── index.py         # Hash-based indexing
├── parser.py        # SQL lexer and parser
├── query.py         # Query execution engine
├── planner.py       # Query planner
├── persistence.py   # JSON serialization
├── types.py         # Type definitions
└── errors.py        # Custom exceptions
```

## Test Suite

MiniDB includes a comprehensive test suite with 95+ test cases:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_queries.py -v

# Run with coverage
python -m pytest tests/ -v --cov=minidb
```

### Test Categories

- **test_database.py**: Database lifecycle and table management
- **test_crud.py**: INSERT, SELECT, UPDATE, DELETE operations
- **test_queries.py**: WHERE, ORDER BY, LIMIT, parser errors, type validation
- **test_aggregations.py**: COUNT, SUM, AVG, MIN, MAX, GROUP BY
- **test_joins.py**: JOIN operations
- **test_index.py**: Indexing and query planning
- **test_persistence.py**: Save/load functionality
- **test_performance.py**: Large dataset tests (10,000+ rows)

## Performance

MiniDB is designed for small to medium datasets:

- **10,000 rows**: All operations complete in under 30 seconds
- **Indexed lookups**: O(1) for primary key equality
- **Range queries**: O(n) with index optimization
- **Table scans**: O(n) for non-indexed columns

## Limitations

- In-memory only (no disk-based storage during operation)
- Single-threaded
- No transactions
- No foreign key constraints
- Limited JOIN support (INNER and LEFT JOIN only, no RIGHT JOIN execution)

## License

MIT License - Use freely for any purpose.

## Contributing

Contributions welcome! Areas for improvement:

- B-tree indexes for range queries
- LEFT/RIGHT OUTER JOIN
- Subqueries
- HAVING clause
- DISTINCT
- More aggregate functions
- Query optimization
- Concurrent access
