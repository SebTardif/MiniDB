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
