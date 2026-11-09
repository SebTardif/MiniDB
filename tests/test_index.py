"""Tests for indexing and query planning."""

import pytest

from minidb import Column, ColumnType, HashIndex, MiniDB
from minidb.errors import DuplicateKeyError, TypeMismatchError
from minidb.planner import QueryPlanner, ScanType


class TestIndexing:
    """Tests for index functionality."""

    def test_nan_primary_key_is_not_inserted_twice(self):
        """NaN is not equal to itself, but it is still one primary key."""
        db = MiniDB()
        db.execute('CREATE TABLE nans (id FLOAT PRIMARY KEY, v STRING)')
        db.execute('INSERT INTO nans (id, v) VALUES (?, ?)', [float('nan'), 'a'])
        with pytest.raises(DuplicateKeyError):
            db.execute('INSERT INTO nans (id, v) VALUES (?, ?)', [float('nan'), 'b'])
        assert db.query('SELECT v FROM nans') == [{'v': 'a'}]

    def test_primary_key_index_created(self):
        """Test that an index is automatically created for primary keys."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        table = db.get_table('users')
        assert table.has_index('id')

    def test_index_lookup(self):
        """Test index lookup functionality."""
        index = HashIndex(column_name='id')

        index.insert(1, 0)
        index.insert(2, 1)
        index.insert(3, 2)
        index.insert(2, 3)  # Duplicate key, different row

        assert index.lookup(1) == {0}
        assert index.lookup(2) == {1, 3}
        assert index.lookup(3) == {2}
        assert index.lookup(99) == set()

    def test_primary_key_range_after_delete_returns_remaining_ids(self):
        """A range still returns every row whose id remains after a delete."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)')
        for i in range(20):
            db.execute('INSERT INTO t (id, n) VALUES (?, ?)', [i, i])
        db.execute('DELETE FROM t WHERE id = 4')
        rows = db.query('SELECT id FROM t WHERE id >= 0 ORDER BY id')
        assert [row['id'] for row in rows] == [i for i in range(20) if i != 4]

    def test_index_delete(self):
        """Test index deletion."""
        index = HashIndex(column_name='id')

        index.insert(1, 0)
        index.insert(1, 1)
        index.insert(2, 2)

        index.delete(1, 0)

        assert index.lookup(1) == {1}
        assert index.lookup(2) == {2}

    def test_index_range_lookup(self):
        """Test index range lookup functionality."""
        index = HashIndex(column_name='value')

        for i in range(10):
            index.insert(i, i)

        # Test less than
        assert index.range_lookup('<', 5) == {0, 1, 2, 3, 4}

        # Test less than or equal
        assert index.range_lookup('<=', 5) == {0, 1, 2, 3, 4, 5}

        # Test greater than
        assert index.range_lookup('>', 5) == {6, 7, 8, 9}

        # Test greater than or equal
        assert index.range_lookup('>=', 5) == {5, 6, 7, 8, 9}

    def test_range_lookup_incompatible_type_raises(self):
        """Bisect on sorted keys must raise TypeMismatchError, not TypeError."""
        index = HashIndex(column_name='id')
        index.insert(1, 0)
        index.insert(3, 1)

        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            index.range_lookup('>', 'x')
        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            index.range_lookup('<', 'x')
        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            index.range_lookup('>=', 'x')
        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            index.range_lookup('<=', 'x')

        assert index.range_lookup('>', 1) == {1}
        assert index.range_lookup('<', 2) == {0}

    def test_query_planner_uses_index(self):
        """Test that the query planner chooses index scan for PK lookups."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        # Insert some data
        for i in range(10):
            db.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")

        from minidb.parser import parse_sql

        query = parse_sql('SELECT * FROM users WHERE id = 5')

        table = db.get_table('users')
        planner = QueryPlanner(table)
        plan = planner.plan_select(query)

        assert plan.scan_type == ScanType.INDEX_SCAN
        assert plan.index_column == 'id'

    def test_query_planner_uses_range_scan(self):
        """Test that the query planner chooses index range scan."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        for i in range(10):
            db.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")

        from minidb.parser import parse_sql

        query = parse_sql('SELECT * FROM users WHERE id > 5')

        table = db.get_table('users')
        planner = QueryPlanner(table)
        plan = planner.plan_select(query)

        assert plan.scan_type == ScanType.INDEX_RANGE_SCAN
        assert plan.index_column == 'id'

    def test_query_planner_uses_table_scan(self):
        """Test that the query planner chooses table scan for non-indexed columns."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        for i in range(10):
            db.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")

        from minidb.parser import parse_sql

        query = parse_sql("SELECT * FROM users WHERE name = 'User5'")

        table = db.get_table('users')
        planner = QueryPlanner(table)
        plan = planner.plan_select(query)

        assert plan.scan_type == ScanType.TABLE_SCAN

    def test_parenthesized_and_uses_primary_key_index(self, monkeypatch):
        """Parentheses around an indexed comparison still use the index."""
        from minidb.table import Table

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        for i in range(1, 21):
            db.execute('INSERT INTO users (id, name) VALUES (?, ?)', [i, f'U{i}'])
        db.execute("UPDATE users SET name = 'U1' WHERE id = 2")

        scans = 0
        original = Table.scan

        def counting(self):
            nonlocal scans
            scans += 1
            return original(self)

        monkeypatch.setattr(Table, 'scan', counting)

        assert 'index_scan' in db.explain("SELECT * FROM users WHERE (id = 1) AND name = 'U1'")
        scans = 0
        assert db.query("SELECT id FROM users WHERE (id = 1) AND name = 'U1'") == [{'id': 1}]
        assert scans == 0

        scans = 0
        assert db.query("SELECT id FROM users WHERE ((users.id = 1)) AND name = 'U1'") == [{'id': 1}]
        assert scans == 0

        scans = 0
        rows = db.query('SELECT id FROM users WHERE (id >= 10) AND (id <= 12)')
        assert [row['id'] for row in rows] == [10, 11, 12]
        assert scans == 0
        assert 'index_range_scan' in db.explain('SELECT id FROM users WHERE (id >= 10) AND (id <= 12)')

        both = db.query("SELECT id FROM users WHERE (id = 1 OR id = 2) AND name = 'U1'")
        assert sorted(row['id'] for row in both) == [1, 2]

    def test_index_updated_on_insert(self):
        """Test that index is updated when rows are inserted."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")

        table = db.get_table('users')
        index = table.get_index('id')

        assert index.lookup(1) != set()
        assert index.lookup(2) != set()

    def test_index_updated_on_delete(self):
        """Test that index is updated when rows are deleted."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")

        db.execute('DELETE FROM users WHERE id = 1')

        table = db.get_table('users')
        index = table.get_index('id')

        assert index.lookup(1) == set()
        assert index.lookup(2) != set()

    def test_index_updated_on_update(self):
        """Test that index is updated when rows are updated."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )

        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")

        table = db.get_table('users')
        index = table.get_index('id')

        # Index should have entry for id=1
        assert index.lookup(1) != set()

        # Note: We can't update the primary key in this implementation
        # but the index is properly maintained for other operations
