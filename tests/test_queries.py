"""Tests for WHERE, ORDER BY, GROUP BY queries."""

import sys

import pytest

sys.path.insert(0, '/home/sebtardif/MiniDB')

from minidb import Column, ColumnType, MiniDB
from minidb.errors import SyntaxError_


class TestParserErrors:
    """Tests for SQL parsing error paths."""

    def test_syntax_error_unexpected_token(self):
        """Test that malformed SQL raises SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('SELECTX * FROM users')

    def test_syntax_error_unterminated_string(self):
        """Test that an unterminated string literal raises SyntaxError_."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(SyntaxError_, match='Unterminated string'):
            db.execute("INSERT INTO t (id, v) VALUES (1, 'hello)")

    def test_syntax_error_unexpected_character(self):
        """Test that unexpected characters raise SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('SELECT * FROM t WHERE id @ 1')

    def test_empty_sql(self):
        """Test that empty SQL raises SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('')


class TestTypeValidation:
    """Tests for type validation and NULL constraint errors."""

    def test_null_value_on_primary_key(self):
        """Test inserting NULL into a non-nullable primary key column."""
        from minidb.errors import NullValueError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(NullValueError):
            db.execute("INSERT INTO t (id, v) VALUES (NULL, 'hello')")

    def test_insert_with_missing_nullable_column(self):
        """Test that missing nullable columns default to NULL."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        db.execute('INSERT INTO t (id) VALUES (1)')
        results = db.query('SELECT * FROM t WHERE id = 1')
        assert len(results) == 1
        assert results[0]['v'] is None

    def test_duplicate_primary_key_error_message(self):
        """Test that DuplicateKeyError includes the key value."""
        from minidb.errors import DuplicateKeyError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO t (id) VALUES (42)')
        with pytest.raises(DuplicateKeyError) as exc_info:
            db.execute('INSERT INTO t (id) VALUES (42)')
        assert '42' in str(exc_info.value)


class TestWhereClause:
    """Tests for WHERE clause operations."""

    @pytest.fixture
    def db(self):
        """Create a populated test database."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
                Column('age', ColumnType.INTEGER),
                Column('salary', ColumnType.FLOAT),
                Column('active', ColumnType.BOOLEAN),
            ],
        )

        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (3, 'Charlie', 35, 55000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (4, 'Diana', 28, 48000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (5, 'Eve', 32, 52000.0, false)")

        return db

    def test_where_equality(self, db):
        """Test WHERE with equality comparison."""
        results = db.query('SELECT * FROM users WHERE id = 1')

        assert len(results) == 1
        assert results[0]['name'] == 'Alice'

    def test_where_greater_than(self, db):
        """Test WHERE with greater than comparison."""
        results = db.query('SELECT * FROM users WHERE age > 30')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_less_than(self, db):
        """Test WHERE with less than comparison."""
        results = db.query('SELECT * FROM users WHERE age < 30')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Diana' in names

    def test_where_greater_equal(self, db):
        """Test WHERE with greater than or equal comparison."""
        results = db.query('SELECT * FROM users WHERE age >= 30')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_less_equal(self, db):
        """Test WHERE with less than or equal comparison."""
        results = db.query('SELECT * FROM users WHERE age <= 30')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Bob' in names
        assert 'Diana' in names

    def test_where_and(self, db):
        """Test WHERE with AND condition."""
        results = db.query('SELECT * FROM users WHERE age > 25 AND active = true')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Diana' in names

    def test_where_or(self, db):
        """Test WHERE with OR condition."""
        results = db.query('SELECT * FROM users WHERE age < 26 OR age > 31')

        # Bob (25), Charlie (35), and Eve (32) match
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_like_prefix(self, db):
        """Test WHERE with LIKE pattern matching (prefix)."""
        results = db.query("SELECT * FROM users WHERE name LIKE 'A%'")

        assert len(results) == 1
        assert results[0]['name'] == 'Alice'

    def test_where_like_suffix(self, db):
        """Test WHERE with LIKE pattern matching (suffix)."""
        results = db.query("SELECT * FROM users WHERE name LIKE '%e'")

        # Alice, Charlie, and Eve all end with 'e'
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_like_contains(self, db):
        """Test WHERE with LIKE pattern matching (contains)."""
        results = db.query("SELECT * FROM users WHERE name LIKE '%a%'")

        # Alice, Charlie, and Diana all contain 'a' (case-insensitive)
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Diana' in names

    def test_where_in(self, db):
        """Test WHERE with IN clause."""
        results = db.query('SELECT * FROM users WHERE id IN (1, 3, 5)')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_not_equals(self, db):
        """Test WHERE with not equals comparison."""
        results = db.query('SELECT * FROM users WHERE active != true')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Eve' in names

    def test_order_by_asc(self, db):
        """Test ORDER BY ascending."""
        results = db.query('SELECT * FROM users ORDER BY age ASC')

        ages = [r['age'] for r in results]
        assert ages == [25, 28, 30, 32, 35]

    def test_order_by_desc(self, db):
        """Test ORDER BY descending."""
        results = db.query('SELECT * FROM users ORDER BY salary DESC')

        salaries = [r['salary'] for r in results]
        assert salaries == [55000.0, 52000.0, 50000.0, 48000.0, 45000.0]

    def test_order_by_with_where(self, db):
        """Test ORDER BY combined with WHERE."""
        results = db.query('SELECT * FROM users WHERE active = true ORDER BY age DESC')

        assert len(results) == 3
        ages = [r['age'] for r in results]
        assert ages == [35, 30, 28]

    def test_limit(self, db):
        """Test LIMIT clause."""
        results = db.query('SELECT * FROM users ORDER BY id LIMIT 2')

        assert len(results) == 2
        assert results[0]['name'] == 'Alice'
        assert results[1]['name'] == 'Bob'

    def test_limit_with_where(self, db):
        """Test LIMIT combined with WHERE."""
        results = db.query('SELECT * FROM users WHERE active = true ORDER BY age ASC LIMIT 1')

        assert len(results) == 1
        assert results[0]['name'] == 'Diana'
