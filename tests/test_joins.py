"""Tests for JOIN operations."""

import pytest
import sys
sys.path.insert(0, '/home/sebtardif/MiniDB')

from minidb import MiniDB, Column, ColumnType


class TestJoins:
    """Tests for JOIN operations."""
    
    @pytest.fixture
    def db(self):
        """Create a test database with users and orders tables."""
        db = MiniDB()
        
        # Users table
        db.create_table('users', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('name', ColumnType.STRING),
            Column('email', ColumnType.STRING),
        ])
        
        db.execute("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')")
        db.execute("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')")
        db.execute("INSERT INTO users (id, name, email) VALUES (3, 'Charlie', 'charlie@example.com')")
        
        # Orders table
        db.create_table('orders', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('user_id', ColumnType.INTEGER),
            Column('product', ColumnType.STRING),
            Column('total', ColumnType.FLOAT),
        ])
        
        db.execute("INSERT INTO orders (id, user_id, product, total) VALUES (1, 1, 'Widget', 29.99)")
        db.execute("INSERT INTO orders (id, user_id, product, total) VALUES (2, 1, 'Gadget', 49.99)")
        db.execute("INSERT INTO orders (id, user_id, product, total) VALUES (3, 2, 'Gizmo', 19.99)")
        db.execute("INSERT INTO orders (id, user_id, product, total) VALUES (4, 2, 'Widget', 29.99)")
        db.execute("INSERT INTO orders (id, user_id, product, total) VALUES (5, 2, 'Gadget', 49.99)")
        # Charlie has no orders
        
        return db
    
    def test_inner_join(self, db):
        """Test basic INNER JOIN."""
        results = db.query("""
            SELECT users.name, orders.product, orders.total
            FROM users
            JOIN orders ON users.id = orders.user_id
        """)
        
        assert len(results) == 5  # Alice has 2 orders, Bob has 3 orders, Charlie has 0
        
        # Check Alice's orders
        alice_orders = [r for r in results if r['name'] == 'Alice']
        assert len(alice_orders) == 2
        
        # Check Bob's orders
        bob_orders = [r for r in results if r['name'] == 'Bob']
        assert len(bob_orders) == 3
        
        # Charlie should not appear (no orders)
        charlie_orders = [r for r in results if r['name'] == 'Charlie']
        assert len(charlie_orders) == 0
    
    def test_join_with_where(self, db):
        """Test JOIN with WHERE clause."""
        results = db.query("""
            SELECT users.name, orders.product
            FROM users
            JOIN orders ON users.id = orders.user_id
            WHERE orders.total > 30
        """)
        
        # Only Gadget orders (49.99 each) are > 30
        # Alice has 1 Gadget order, Bob has 1 Gadget order
        assert len(results) == 2
        products = {r['product'] for r in results}
        assert products == {'Gadget'}
    
    def test_join_with_aggregation(self, db):
        """Test JOIN with aggregation."""
        results = db.query("""
            SELECT name, SUM(total)
            FROM users
            JOIN orders ON users.id = orders.user_id
            GROUP BY name
        """)
        
        assert len(results) == 2  # Only users with orders
        
        totals = {r['name']: r['SUM(total)'] for r in results}
        assert totals['Alice'] == 79.98  # 29.99 + 49.99
        assert totals['Bob'] == 99.97  # 19.99 + 29.99 + 49.99
    
    def test_join_multiple_columns(self, db):
        """Test JOIN selecting multiple columns from both tables."""
        results = db.query("""
            SELECT users.name, users.email, orders.product, orders.total
            FROM users
            JOIN orders ON users.id = orders.user_id
            ORDER BY orders.total DESC
        """)
        
        assert len(results) == 5
        
        # First result should be highest total (Gadget at 49.99)
        assert results[0]['product'] == 'Gadget'
        assert results[0]['total'] == 49.99
    
    def test_join_order_matters(self, db):
        """Test that join order affects which table is the 'left' table."""
        # Join from orders to users
        results = db.query("""
            SELECT orders.product, users.name
            FROM orders
            JOIN users ON orders.user_id = users.id
        """)
        
        assert len(results) == 5
        
        # All results should have valid user names
        for r in results:
            assert r['name'] in ('Alice', 'Bob')
    
    def test_join_count(self, db):
        """Test COUNT with JOIN."""
        results = db.query("""
            SELECT name, COUNT(*)
            FROM users
            JOIN orders ON users.id = orders.user_id
            GROUP BY name
        """)
        
        counts = {r['name']: r['COUNT(*)'] for r in results}
        assert counts['Alice'] == 2
        assert counts['Bob'] == 3
