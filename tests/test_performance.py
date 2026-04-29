"""Tests for performance with large datasets."""

import pytest
import time
import sys
sys.path.insert(0, '/home/sebtardif/MiniDB')

from minidb import MiniDB, Column, ColumnType


class TestPerformance:
    """Tests for performance with 10,000+ rows."""
    
    @pytest.fixture
    def large_db(self):
        """Create a database with 10,000 rows."""
        db = MiniDB()
        
        db.create_table('large_table', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('category', ColumnType.INTEGER),
            Column('value', ColumnType.FLOAT),
            Column('name', ColumnType.STRING),
        ])
        
        # Insert 10,000 rows
        for i in range(10000):
            category = i % 100  # 100 different categories
            value = float(i) * 1.5
            name = f'Item_{i}'
            db.execute(
                f"INSERT INTO large_table (id, category, value, name) "
                f"VALUES ({i}, {category}, {value}, '{name}')"
            )
        
        return db
    
    def test_large_insert_performance(self):
        """Test that inserting 10,000 rows completes in reasonable time."""
        db = MiniDB()
        
        db.create_table('insert_test', [
            Column('id', ColumnType.INTEGER, primary_key=True),
            Column('data', ColumnType.STRING),
        ])
        
        start = time.time()
        
        for i in range(10000):
            db.execute(f"INSERT INTO insert_test (id, data) VALUES ({i}, 'data_{i}')")
        
        elapsed = time.time() - start
        
        # Should complete in under 30 seconds
        assert elapsed < 30, f"Insert took {elapsed:.2f} seconds"
        
        table = db.get_table('insert_test')
        assert table.row_count == 10000
    
    def test_large_select_with_index(self, large_db):
        """Test that indexed SELECT on large table is fast."""
        start = time.time()
        
        # Query using primary key index
        results = large_db.query("SELECT * FROM large_table WHERE id = 5000")
        
        elapsed = time.time() - start
        
        # Should be very fast with index (< 1 second)
        assert elapsed < 1, f"Indexed select took {elapsed:.2f} seconds"
        assert len(results) == 1
        assert results[0]['name'] == 'Item_5000'
    
    def test_large_select_table_scan(self, large_db):
        """Test that table scan SELECT on large table completes."""
        start = time.time()
        
        # Query on non-indexed column (table scan)
        results = large_db.query("SELECT * FROM large_table WHERE category = 50")
        
        elapsed = time.time() - start
        
        # Table scan should still complete in reasonable time
        assert elapsed < 10, f"Table scan took {elapsed:.2f} seconds"
        assert len(results) == 100  # 10000 / 100 categories
    
    def test_large_aggregation(self, large_db):
        """Test GROUP BY aggregation on large dataset."""
        start = time.time()
        
        results = large_db.query("""
            SELECT category, COUNT(*), AVG(value), SUM(value)
            FROM large_table
            GROUP BY category
        """)
        
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 10, f"Aggregation took {elapsed:.2f} seconds"
        
        # Should have 100 categories
        assert len(results) == 100
        
        # Verify aggregation correctness
        for r in results:
            assert r['COUNT(*)'] == 100  # 100 items per category
    
    def test_large_order_by(self, large_db):
        """Test ORDER BY on large dataset."""
        start = time.time()
        
        results = large_db.query("SELECT * FROM large_table ORDER BY value DESC LIMIT 10")
        
        elapsed = time.time() - start
        
        assert elapsed < 10, f"ORDER BY took {elapsed:.2f} seconds"
        assert len(results) == 10
        
        # Results should be in descending order
        values = [r['value'] for r in results]
        assert values == sorted(values, reverse=True)
    
    def test_large_update(self, large_db):
        """Test UPDATE on large dataset."""
        start = time.time()
        
        # Update 100 rows
        affected = large_db.execute("UPDATE large_table SET value = 0.0 WHERE category = 0")
        
        elapsed = time.time() - start
        
        assert elapsed < 5, f"Update took {elapsed:.2f} seconds"
        assert affected == 100
        
        # Verify update
        results = large_db.query("SELECT * FROM large_table WHERE category = 0")
        for r in results:
            assert r['value'] == 0.0
    
    def test_large_delete(self, large_db):
        """Test DELETE on large dataset."""
        start = time.time()
        
        # Delete 100 rows
        affected = large_db.execute("DELETE FROM large_table WHERE category = 99")
        
        elapsed = time.time() - start
        
        assert elapsed < 5, f"Delete took {elapsed:.2f} seconds"
        assert affected == 100
        
        # Verify deletion
        table = large_db.get_table('large_table')
        assert table.row_count == 9900
    
    def test_large_where_with_and(self, large_db):
        """Test WHERE with AND on large dataset."""
        start = time.time()
        
        results = large_db.query("""
            SELECT * FROM large_table
            WHERE category >= 10 AND category < 20
        """)
        
        elapsed = time.time() - start
        
        assert elapsed < 5, f"WHERE AND took {elapsed:.2f} seconds"
        assert len(results) == 1000  # 10 categories * 100 items each
    
    def test_large_where_with_or(self, large_db):
        """Test WHERE with OR on large dataset."""
        start = time.time()
        
        results = large_db.query("""
            SELECT * FROM large_table
            WHERE category = 0 OR category = 50 OR category = 99
        """)
        
        elapsed = time.time() - start
        
        assert elapsed < 5, f"WHERE OR took {elapsed:.2f} seconds"
        assert len(results) == 300  # 3 categories * 100 items each
    
    def test_large_count_all(self, large_db):
        """Test COUNT(*) on large dataset."""
        start = time.time()
        
        results = large_db.query("SELECT COUNT(*) FROM large_table")
        
        elapsed = time.time() - start
        
        assert elapsed < 2, f"COUNT took {elapsed:.2f} seconds"
        assert results[0]['COUNT(*)'] == 10000
    
    def test_large_sum(self, large_db):
        """Test SUM on large dataset."""
        start = time.time()
        
        results = large_db.query("SELECT SUM(value) FROM large_table")
        
        elapsed = time.time() - start
        
        assert elapsed < 2, f"SUM took {elapsed:.2f} seconds"
        
        # Expected sum: sum of i*1.5 for i from 0 to 9999
        expected = sum(i * 1.5 for i in range(10000))
        assert abs(results[0]['SUM(value)'] - expected) < 0.01
