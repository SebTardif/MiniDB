"""Tests for database lifecycle and table management."""

import pytest

from minidb import Column, ColumnType, InvalidQueryError, MiniDB, QueryExecutor, TableExistsError, TableNotFoundError
from minidb.parser import parse_sql


class TestDatabaseLifecycle:
    """Tests for database creation and management."""

    def test_create_database(self):
        """Test creating an empty database."""
        db = MiniDB()
        assert len(db) == 0
        assert db.tables == []

    def test_create_table(self):
        """Test creating a table with various column types."""
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

        assert len(db) == 1
        assert 'users' in db

        table = db.get_table('users')
        assert table is not None
        assert table.row_count == 0
        assert table.primary_key == 'id'
        assert len(table.columns) == 5

    def test_create_table_sql(self):
        """Test creating a table using SQL."""
        db = MiniDB()

        db.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name STRING,
                price FLOAT,
                in_stock BOOLEAN
            )
        """)

        assert 'products' in db
        table = db.get_table('products')
        assert table.primary_key == 'id'

    def test_query_executor_create_table_points_at_minidb_execute(self):
        """QueryExecutor CREATE TABLE tells the caller to use MiniDB.execute()."""
        executor = QueryExecutor({})
        with pytest.raises(InvalidQueryError, match=r'MiniDB.execute'):
            executor.execute(parse_sql('CREATE TABLE t (id INTEGER PRIMARY KEY)'))

    def test_query_executor_drop_table_points_at_minidb_execute(self):
        """QueryExecutor DROP TABLE tells the caller to use MiniDB.execute()."""
        executor = QueryExecutor({})
        with pytest.raises(InvalidQueryError, match=r'MiniDB.execute'):
            executor.execute(parse_sql('DROP TABLE t'))

    def test_table_exists_error(self):
        """Test that creating a duplicate table raises an error."""
        db = MiniDB()

        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
            ],
        )

        with pytest.raises(TableExistsError):
            db.create_table(
                'users',
                [
                    Column('id', ColumnType.INTEGER, primary_key=True),
                ],
            )

    def test_drop_table(self):
        """Test dropping a table."""
        db = MiniDB()

        db.create_table(
            'temp',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
            ],
        )

        assert 'temp' in db
        db.drop_table('temp')
        assert 'temp' not in db

    def test_drop_table_not_found(self):
        """Test dropping a non-existent table raises an error."""
        db = MiniDB()

        with pytest.raises(TableNotFoundError):
            db.drop_table('nonexistent')

    def test_drop_table_sql(self):
        """Test dropping a table using SQL."""
        db = MiniDB()
        db.execute('CREATE TABLE temp (id INTEGER PRIMARY KEY, value STRING)')
        assert 'temp' in db
        db.execute('DROP TABLE temp')
        assert 'temp' not in db

    def test_query_on_non_select(self):
        """Test that query() raises MiniDBError for non-SELECT statements."""
        from minidb.errors import MiniDBError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(MiniDBError, match=r'query\(\) only runs SELECT'):
            db.query("INSERT INTO t (id, v) VALUES (1, 'x')")

    def test_query_insert_mentions_execute(self):
        """INSERT via query() tells the caller to use execute()."""
        from minidb.errors import MiniDBError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(MiniDBError, match=r'use execute\(\)'):
            db.query("INSERT INTO t (id, v) VALUES (1, 'x')")

    def test_repr(self):
        """Test __repr__ on MiniDB."""
        db = MiniDB()
        assert repr(db) == 'MiniDB()'
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO users (id) VALUES (1)')
        assert 'users(1 rows)' in repr(db)

    def test_insert_into_nonexistent_table(self):
        """Test INSERT into a table that does not exist raises error."""
        db = MiniDB()
        with pytest.raises(TableNotFoundError):
            db.execute('INSERT INTO ghost (id) VALUES (1)')

    def test_update_nonexistent_table(self):
        """Test UPDATE on a table that does not exist raises error."""
        db = MiniDB()
        with pytest.raises(TableNotFoundError):
            db.execute('UPDATE ghost SET id = 1')

    def test_delete_from_nonexistent_table(self):
        """Test DELETE from a table that does not exist raises error."""
        db = MiniDB()
        with pytest.raises(TableNotFoundError):
            db.execute('DELETE FROM ghost')

    def test_select_from_nonexistent_table(self):
        """Test SELECT from a table that does not exist raises error."""
        db = MiniDB()
        with pytest.raises(TableNotFoundError):
            db.query('SELECT * FROM ghost')


class TestExplain:
    """Tests for MiniDB.explain()."""

    def test_explain_pk_equality_uses_index_scan(self):
        """PK equality WHERE id = 1 plans an index_scan."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        plan = db.explain('SELECT * FROM users WHERE id = 1')
        assert 'index_scan' in plan

    def test_explain_unindexed_column_uses_table_scan(self):
        """An unindexed column plans a table_scan."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        plan = db.explain("SELECT * FROM users WHERE name = 'Alice'")
        assert 'table_scan' in plan

    def test_explain_insert_raises(self):
        """explain() is SELECT-only."""
        from minidb.errors import MiniDBError

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        with pytest.raises(MiniDBError, match='SELECT-only'):
            db.explain("INSERT INTO users (id, name) VALUES (2, 'Bob')")

    def test_explain_binds_params_before_planning(self):
        """explain() binds ? so a parameterized PK lookup still plans an index_scan."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        plan = db.explain('SELECT * FROM users WHERE id = ?', [1])
        assert 'index_scan' in plan


class TestParameters:
    """Tests for ? placeholders bound after parse."""

    @pytest.fixture
    def db(self):
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        return db

    def test_insert_with_placeholders(self, db):
        """INSERT binds one ? per value."""
        row_id = db.execute('INSERT INTO users (id, name, age) VALUES (?, ?, ?)', [1, 'Alice', 30])
        assert row_id == 0
        results = db.query('SELECT * FROM users')
        assert len(results) == 1
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'
        assert results[0]['age'] == 30

    def test_select_where_id_param(self, db):
        """SELECT WHERE id = ? binds the id."""
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
        results = db.query('SELECT name FROM users WHERE id = ?', [2])
        assert len(results) == 1
        assert results[0]['name'] == 'Bob'

    def test_select_where_name_param(self, db):
        """SELECT WHERE name = ? binds the name."""
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
        results = db.query('SELECT id FROM users WHERE name = ?', ['Alice'])
        assert len(results) == 1
        assert results[0]['id'] == 1

    def test_update_set_and_where_params(self, db):
        """UPDATE SET name = ? WHERE id = ? binds SET then WHERE."""
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        affected = db.execute('UPDATE users SET name = ? WHERE id = ?', ['Alicia', 1])
        assert affected == 1
        results = db.query('SELECT name FROM users WHERE id = 1')
        assert results[0]['name'] == 'Alicia'

    def test_in_placeholders(self, db):
        """WHERE id IN (?, ?) binds both list values."""
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
        db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Charlie', 35)")
        results = db.query('SELECT name FROM users WHERE id IN (?, ?) ORDER BY name', [1, 3])
        assert [r['name'] for r in results] == ['Alice', 'Charlie']

    def test_too_few_params(self, db):
        """Fewer params than placeholders raises InvalidQueryError."""
        with pytest.raises(InvalidQueryError, match=r'expected 3 parameters, got 1'):
            db.execute('INSERT INTO users (id, name, age) VALUES (?, ?, ?)', [1])

    def test_too_many_params(self, db):
        """More params than placeholders raises InvalidQueryError."""
        with pytest.raises(InvalidQueryError, match=r'expected 2 parameters, got 3'):
            db.execute('INSERT INTO users (id, name) VALUES (?, ?)', [1, 'Alice', 99])

    def test_params_on_literal_query(self, db):
        """Params supplied to a statement with no ? raise InvalidQueryError."""
        with pytest.raises(InvalidQueryError, match=r'expected 0 parameters, got 1'):
            db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')", [1])

    def test_execute_without_params_still_works(self, db):
        """Existing no-params execute and query still work."""
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        results = db.query('SELECT name FROM users WHERE id = 1')
        assert results[0]['name'] == 'Alice'

    def test_placeholder_is_bound_not_interpolated(self, db):
        """A value that looks like SQL is stored as a string, not executed."""
        payload = "'; DROP TABLE users; --"
        db.execute('INSERT INTO users (id, name, age) VALUES (?, ?, ?)', [1, payload, 30])
        results = db.query('SELECT name FROM users WHERE id = ?', [1])
        assert results[0]['name'] == payload
        assert 'users' in db
        assert db.get_table('users').row_count == 1


class TestTransactions:
    """Tests for in-memory snapshot BEGIN / COMMIT / ROLLBACK."""

    @pytest.fixture
    def db(self):
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        return db

    def test_begin_insert_rollback_discards_insert(self, db):
        """BEGIN, INSERT, ROLLBACK leaves the insert gone."""
        db.execute('BEGIN')
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        assert db.get_table('users').row_count == 2
        db.execute('ROLLBACK')
        results = db.query('SELECT id, name FROM users ORDER BY id')
        assert [r['name'] for r in results] == ['Alice']

    def test_begin_insert_commit_keeps_insert(self, db):
        """BEGIN, INSERT, COMMIT leaves the insert in place."""
        db.execute('BEGIN')
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        db.execute('COMMIT')
        results = db.query('SELECT id, name FROM users ORDER BY id')
        assert [r['name'] for r in results] == ['Alice', 'Bob']

    def test_commit_without_begin_raises(self, db):
        """COMMIT without BEGIN raises InvalidQueryError."""
        with pytest.raises(InvalidQueryError):
            db.execute('COMMIT')

    def test_rollback_without_begin_raises(self, db):
        """ROLLBACK without BEGIN raises InvalidQueryError."""
        with pytest.raises(InvalidQueryError):
            db.execute('ROLLBACK')

    def test_nested_begin_raises(self, db):
        """BEGIN while already in a transaction raises InvalidQueryError."""
        db.execute('BEGIN')
        with pytest.raises(InvalidQueryError):
            db.execute('BEGIN')
        db.execute('ROLLBACK')

    def test_begin_drop_table_rollback_restores_table(self, db):
        """BEGIN, DROP TABLE, ROLLBACK restores the table and its rows."""
        db.execute('BEGIN')
        db.execute('DROP TABLE users')
        assert 'users' not in db
        db.execute('ROLLBACK')
        assert 'users' in db
        results = db.query('SELECT name FROM users')
        assert [r['name'] for r in results] == ['Alice']

    def test_begin_create_table_rollback_drops_table(self, db):
        """BEGIN, CREATE TABLE, ROLLBACK removes the new table."""
        db.execute('BEGIN')
        db.execute('CREATE TABLE extra (id INTEGER PRIMARY KEY)')
        assert 'extra' in db
        db.execute('ROLLBACK')
        assert 'extra' not in db

    def test_begin_update_rollback_restores_values(self, db):
        """BEGIN, UPDATE, ROLLBACK restores the old column values."""
        db.execute('BEGIN')
        db.execute("UPDATE users SET name = 'Alicia' WHERE id = 1")
        assert db.query('SELECT name FROM users WHERE id = 1')[0]['name'] == 'Alicia'
        db.execute('ROLLBACK')
        assert db.query('SELECT name FROM users WHERE id = 1')[0]['name'] == 'Alice'
