"""Tests for INSERT, SELECT, UPDATE, DELETE operations."""

import pytest

from minidb import Column, ColumnType, DuplicateKeyError, MiniDB


class TestCRUD:
    """Tests for CRUD operations."""

    @pytest.fixture
    def db(self):
        """Create a test database with a users table."""
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
        return db

    def test_insert_single_row(self, db):
        """Test inserting a single row."""
        row_id = db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")

        assert row_id == 0  # First row ID

        table = db.get_table('users')
        assert table.row_count == 1

        row = table.get_row_by_id(row_id)
        assert row['id'] == 1
        assert row['name'] == 'Alice'
        assert row['age'] == 30
        assert row['salary'] == 50000.0
        assert row['active'] is True

    def test_insert_multiple_rows(self, db):
        """Test inserting multiple rows."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (3, 'Charlie', 35, 55000.0, true)")

        table = db.get_table('users')
        assert table.row_count == 3

    def test_insert_duplicate_key(self, db):
        """Test that inserting a duplicate primary key raises an error."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")

        with pytest.raises(DuplicateKeyError):
            db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Bob', 25, 45000.0, false)")

    def test_select_all(self, db):
        """Test SELECT * behavior."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")

        results = db.query('SELECT * FROM users')

        assert len(results) == 2
        assert results[0]['name'] == 'Alice'
        assert results[1]['name'] == 'Bob'

    def test_select_specific_columns(self, db):
        """Test selecting specific columns."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")

        results = db.query('SELECT name, age FROM users')

        assert len(results) == 1
        assert 'name' in results[0]
        assert 'age' in results[0]
        assert 'id' not in results[0]
        assert 'salary' not in results[0]

    def test_update_single_row(self, db):
        """Test updating a single row."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")

        affected = db.execute('UPDATE users SET salary = 60000.0 WHERE id = 1')

        assert affected == 1

        results = db.query('SELECT salary FROM users WHERE id = 1')
        assert results[0]['salary'] == 60000.0

    def test_update_multiple_rows(self, db):
        """Test updating multiple rows."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (3, 'Charlie', 35, 55000.0, true)")

        affected = db.execute('UPDATE users SET active = false WHERE active = true')

        assert affected == 3

    def test_delete_single_row(self, db):
        """Test deleting a single row."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")

        affected = db.execute('DELETE FROM users WHERE id = 1')

        assert affected == 1

        results = db.query('SELECT * FROM users')
        assert len(results) == 1
        assert results[0]['name'] == 'Bob'

    def test_delete_multiple_rows(self, db):
        """Test deleting multiple rows."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (3, 'Charlie', 35, 55000.0, true)")

        affected = db.execute('DELETE FROM users WHERE active = true')

        assert affected == 2

        results = db.query('SELECT * FROM users')
        assert len(results) == 1
        assert results[0]['name'] == 'Bob'

    def test_delete_all_rows(self, db):
        """Test deleting all rows."""
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")

        affected = db.execute('DELETE FROM users')

        assert affected == 2

        table = db.get_table('users')
        assert table.row_count == 0
