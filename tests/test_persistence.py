"""Tests for persistence functionality."""

import os
import tempfile

import pytest

from minidb import Column, ColumnType, MiniDB
from minidb.errors import DuplicateKeyError, TypeMismatchError


class TestPersistence:
    """Tests for save/load functionality."""

    def test_save_and_load(self):
        """Test saving and loading a database."""
        db = MiniDB()

        # Create tables
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
                Column('age', ColumnType.INTEGER),
            ],
        )

        db.create_table(
            'orders',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('user_id', ColumnType.INTEGER),
                Column('total', ColumnType.FLOAT),
            ],
        )

        # Insert data
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
        db.execute('INSERT INTO orders (id, user_id, total) VALUES (1, 1, 99.99)')
        db.execute('INSERT INTO orders (id, user_id, total) VALUES (2, 2, 149.99)')

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)

            # Load into new database
            loaded_db = MiniDB.load(filepath)

            # Verify tables exist
            assert 'users' in loaded_db
            assert 'orders' in loaded_db

            # Verify data
            users = loaded_db.query('SELECT * FROM users')
            assert len(users) == 2

            orders = loaded_db.query('SELECT * FROM orders')
            assert len(orders) == 2

            # Verify specific data
            alice = loaded_db.query('SELECT * FROM users WHERE id = 1')
            assert len(alice) == 1
            assert alice[0]['name'] == 'Alice'
            assert alice[0]['age'] == 30
        finally:
            os.unlink(filepath)

    def test_persistence_with_various_types(self):
        """Test persistence with all column types."""
        db = MiniDB()

        db.create_table(
            'mixed',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('int_col', ColumnType.INTEGER),
                Column('str_col', ColumnType.STRING),
                Column('float_col', ColumnType.FLOAT),
                Column('bool_col', ColumnType.BOOLEAN),
            ],
        )

        db.execute("INSERT INTO mixed (id, int_col, str_col, float_col, bool_col) VALUES (1, 42, 'hello', 3.14, true)")
        db.execute(
            "INSERT INTO mixed (id, int_col, str_col, float_col, bool_col) VALUES (2, -10, 'world', 2.718, false)"
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            loaded_db = MiniDB.load(filepath)

            results = loaded_db.query('SELECT * FROM mixed ORDER BY id')

            assert len(results) == 2
            assert results[0]['int_col'] == 42
            assert results[0]['str_col'] == 'hello'
            assert abs(results[0]['float_col'] - 3.14) < 0.001
            assert results[0]['bool_col'] is True

            assert results[1]['int_col'] == -10
            assert results[1]['str_col'] == 'world'
            assert abs(results[1]['float_col'] - 2.718) < 0.001
            assert results[1]['bool_col'] is False
        finally:
            os.unlink(filepath)

    def test_persistence_preserves_indexes(self):
        """Test that loaded database has working indexes."""
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

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            loaded_db = MiniDB.load(filepath)

            # Check that index exists and works
            table = loaded_db.get_table('users')
            assert table.has_index('id')

            # Query should use index (fast lookup)
            result = loaded_db.query('SELECT * FROM users WHERE id = 5')
            assert len(result) == 1
            assert result[0]['name'] == 'User5'
        finally:
            os.unlink(filepath)

    def test_persistence_empty_database(self):
        """Test saving and loading an empty database."""
        db = MiniDB()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            loaded_db = MiniDB.load(filepath)

            assert len(loaded_db) == 0
            assert loaded_db.tables == []
        finally:
            os.unlink(filepath)

    def test_persistence_file_not_found(self):
        """Test loading from non-existent file raises error."""
        from minidb.errors import FileReadError

        with pytest.raises(FileReadError):
            MiniDB.load('/nonexistent/path/to/file.json')

    def test_persistence_version_mismatch(self):
        """Test loading a file with incompatible version raises error."""
        import json

        from minidb.errors import VersionMismatchError

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
            json.dump({'version': '99.0', 'tables': {}}, f)

        try:
            with pytest.raises(VersionMismatchError) as exc_info:
                MiniDB.load(filepath)
            assert '99.0' in str(exc_info.value)
        finally:
            os.unlink(filepath)

    def test_persistence_invalid_json(self):
        """Test loading a file with invalid JSON raises error."""
        from minidb.errors import FileReadError

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
            f.write('not valid json {{{')

        try:
            with pytest.raises(FileReadError) as exc_info:
                MiniDB.load(filepath)
            assert 'Invalid JSON' in str(exc_info.value)
        finally:
            os.unlink(filepath)

    def test_load_rejects_non_utf8(self):
        """A file that is not UTF-8 is a read error, not UnicodeDecodeError."""
        from minidb.errors import FileReadError

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
            filepath = f.name
            f.write(b'\xff\xfe not json')

        try:
            with pytest.raises(FileReadError) as exc_info:
                MiniDB.load(filepath)
            assert 'UTF-8' in str(exc_info.value)
        finally:
            os.unlink(filepath)

    def test_persistence_write_to_readonly_path(self):
        """Test saving to an unwritable path raises error."""
        from minidb.errors import FileWriteError

        db = MiniDB()
        with pytest.raises(FileWriteError):
            db.save('/nonexistent/directory/file.json')

    def test_json_format_readable(self):
        """Test that saved JSON is human-readable."""
        db = MiniDB()

        db.create_table(
            'simple',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('value', ColumnType.STRING),
            ],
        )

        db.execute("INSERT INTO simple (id, value) VALUES (1, 'test')")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)

            # Read and verify JSON structure
            import json

            with open(filepath) as f:
                data = json.load(f)

            assert 'version' in data
            assert 'tables' in data
            assert 'simple' in data['tables']
            assert data['tables']['simple']['rows'][0]['value'] == 'test'
        finally:
            os.unlink(filepath)

    def test_save_load_preserves_row_ids_after_delete(self):
        """The row id returned by INSERT still finds that row after delete, save, and load."""
        import json

        from minidb.persistence import CURRENT_VERSION

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        first = db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        second = db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        assert isinstance(first, int)
        assert isinstance(second, int)
        db.execute('DELETE FROM users WHERE id = 1')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            with open(filepath, encoding='utf-8') as f:
                saved = json.load(f)
            assert saved['version'] == '1.0'
            assert CURRENT_VERSION == '1.0'
            assert saved['tables']['users']['row_ids'] == [second]
            assert saved['tables']['users']['next_row_id'] == second + 1

            loaded = MiniDB.load(filepath)
            table = loaded.get_table('users')
            assert table.get_row_by_id(second) == {'id': 2, 'name': 'Bob'}
            assert table.get_row_by_id(first) is None
            third = loaded.execute("INSERT INTO users (id, name) VALUES (3, 'Cara')")
            assert third == second + 1
            assert table.get_row_by_id(third) == {'id': 3, 'name': 'Cara'}
        finally:
            os.unlink(filepath)

    def test_load_without_row_ids_uses_sequential_ids(self):
        """A file from before row_ids existed still loads with range ids."""
        import json

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            with open(filepath, encoding='utf-8') as f:
                saved = json.load(f)
            saved['tables']['users'].pop('row_ids', None)
            assert saved['version'] == '1.0'
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(saved, f)

            loaded = MiniDB.load(filepath)
            table = loaded.get_table('users')
            assert table.get_row_by_id(0) == {'id': 1, 'name': 'Alice'}
            assert table.get_row_by_id(1) == {'id': 2, 'name': 'Bob'}
            assert table.get_row_by_id(2) is None
        finally:
            os.unlink(filepath)

    def test_load_rejects_duplicate_primary_key(self):
        """A hand-edited snapshot cannot contain two rows with the same id."""
        import json

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            with open(filepath, encoding='utf-8') as f:
                saved = json.load(f)
            users = saved['tables']['users']
            users['rows'].append({'id': 1, 'name': 'dup'})
            users['row_ids'].append(1)
            users['next_row_id'] = 2
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(saved, f)

            with pytest.raises(DuplicateKeyError):
                MiniDB.load(filepath)
        finally:
            os.unlink(filepath)

    def test_load_rejects_untyped_primary_key(self):
        """A primary key the column cannot store raises, instead of TypeError."""
        import json

        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            db.save(filepath)
            with open(filepath, encoding='utf-8') as f:
                saved = json.load(f)
            users = saved['tables']['users']
            users['rows'].append({'id': 'x', 'name': 'bad'})
            users['row_ids'].append(1)
            users['next_row_id'] = 2
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(saved, f)

            with pytest.raises(TypeMismatchError):
                MiniDB.load(filepath)
        finally:
            os.unlink(filepath)
