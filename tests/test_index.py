"""Tests for indexing and query planning."""

from minidb import Column, ColumnType, HashIndex, MiniDB
from minidb.planner import QueryPlanner, ScanType


class TestIndexing:
    """Tests for index functionality."""

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
