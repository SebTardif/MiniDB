"""Tests for database lifecycle and table management."""

import sys

import pytest

sys.path.insert(0, '/home/sebtardif/MiniDB')

from minidb import Column, ColumnType, MiniDB, TableExistsError, TableNotFoundError


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
