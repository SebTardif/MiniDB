"""Tests for persistence functionality."""

import pytest
import os
import tempfile
import sys
sys.path.insert(0, '/home/sebtardif/MiniDB')

from minidb import MiniDB, Column, ColumnType


class TestPersistence:
    """Tests for save/load functionality."""
    
    def test_save_and_load(self):
        """Test saving and loading a database."""
        db = MiniDB()
        
        # Create tables
        db.create_table('users', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('name', ColumnType.STRING),
            Column('age', ColumnType.INTEGER),
        ])
        
        db.create_table('orders', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('user_id', ColumnType.INTEGER),
            Column('total', ColumnType.FLOAT),
        ])
        
        # Insert data
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Bob', 25)")
        db.execute("INSERT INTO orders (id, user_id, total) VALUES (1, 1, 99.99)")
        db.execute("INSERT INTO orders (id, user_id, total) VALUES (2, 2, 149.99)")
        
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
            users = loaded_db.query("SELECT * FROM users")
            assert len(users) == 2
            
            orders = loaded_db.query("SELECT * FROM orders")
            assert len(orders) == 2
            
            # Verify specific data
            alice = loaded_db.query("SELECT * FROM users WHERE id = 1")
            assert len(alice) == 1
            assert alice[0]['name'] == 'Alice'
            assert alice[0]['age'] == 30
        finally:
            os.unlink(filepath)
    
    def test_persistence_with_various_types(self):
        """Test persistence with all column types."""
        db = MiniDB()
        
        db.create_table('mixed', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('int_col', ColumnType.INTEGER),
            Column('str_col', ColumnType.STRING),
            Column('float_col', ColumnType.FLOAT),
            Column('bool_col', ColumnType.BOOLEAN),
        ])
        
        db.execute("INSERT INTO mixed (id, int_col, str_col, float_col, bool_col) VALUES (1, 42, 'hello', 3.14, true)")
        db.execute("INSERT INTO mixed (id, int_col, str_col, float_col, bool_col) VALUES (2, -10, 'world', 2.718, false)")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            db.save(filepath)
            loaded_db = MiniDB.load(filepath)
            
            results = loaded_db.query("SELECT * FROM mixed ORDER BY id")
            
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
        
        db.create_table('users', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('name', ColumnType.STRING),
        ])
        
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
            result = loaded_db.query("SELECT * FROM users WHERE id = 5")
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
    
    def test_json_format_readable(self):
        """Test that saved JSON is human-readable."""
        db = MiniDB()
        
        db.create_table('simple', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('value', ColumnType.STRING),
        ])
        
        db.execute("INSERT INTO simple (id, value) VALUES (1, 'test')")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            db.save(filepath)
            
            # Read and verify JSON structure
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert 'version' in data
            assert 'tables' in data
            assert 'simple' in data['tables']
            assert data['tables']['simple']['rows'][0]['value'] == 'test'
        finally:
            os.unlink(filepath)
