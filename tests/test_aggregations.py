"""Tests for aggregation functions."""

import pytest

from minidb import Column, ColumnType, MiniDB


class TestAggregations:
    """Tests for aggregation functions."""

    @pytest.fixture
    def db(self):
        """Create a populated test database."""
        db = MiniDB()
        db.create_table(
            'sales',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('product', ColumnType.STRING),
                Column('category', ColumnType.STRING),
                Column('quantity', ColumnType.INTEGER),
                Column('price', ColumnType.FLOAT),
            ],
        )

        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (1, 'Widget', 'A', 10, 9.99)")
        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (2, 'Gadget', 'A', 5, 19.99)")
        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (3, 'Gizmo', 'B', 20, 4.99)")
        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (4, 'Widget', 'B', 15, 9.99)")
        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (5, 'Gadget', 'A', 8, 19.99)")
        db.execute("INSERT INTO sales (id, product, category, quantity, price) VALUES (6, 'Gizmo', 'B', 12, 4.99)")

        return db

    def test_count_all(self, db):
        """Test COUNT(*) function."""
        results = db.query('SELECT COUNT(*) FROM sales')

        assert len(results) == 1
        assert results[0]['COUNT(*)'] == 6

    def test_count_column(self, db):
        """Test COUNT(column) function."""
        results = db.query('SELECT COUNT(product) FROM sales')

        assert len(results) == 1
        assert results[0]['COUNT(product)'] == 6

    def test_sum(self, db):
        """Test SUM function."""
        results = db.query('SELECT SUM(quantity) FROM sales')

        assert len(results) == 1
        assert results[0]['SUM(quantity)'] == 70  # 10+5+20+15+8+12

    def test_avg(self, db):
        """Test AVG function."""
        results = db.query('SELECT AVG(price) FROM sales')

        assert len(results) == 1
        expected_avg = (9.99 + 19.99 + 4.99 + 9.99 + 19.99 + 4.99) / 6
        assert abs(results[0]['AVG(price)'] - expected_avg) < 0.01

    def test_min(self, db):
        """Test MIN function."""
        results = db.query('SELECT MIN(price) FROM sales')

        assert len(results) == 1
        assert results[0]['MIN(price)'] == 4.99

    def test_max(self, db):
        """Test MAX function."""
        results = db.query('SELECT MAX(quantity) FROM sales')

        assert len(results) == 1
        assert results[0]['MAX(quantity)'] == 20

    def test_group_by_count(self, db):
        """Test GROUP BY with COUNT."""
        results = db.query('SELECT category, COUNT(*) FROM sales GROUP BY category')

        assert len(results) == 2
        cat_counts = {r['category']: r['COUNT(*)'] for r in results}
        assert cat_counts['A'] == 3
        assert cat_counts['B'] == 3

    def test_group_by_sum(self, db):
        """Test GROUP BY with SUM."""
        results = db.query('SELECT category, SUM(quantity) FROM sales GROUP BY category')

        assert len(results) == 2
        cat_sums = {r['category']: r['SUM(quantity)'] for r in results}
        assert cat_sums['A'] == 23  # 10+5+8
        assert cat_sums['B'] == 47  # 20+15+12

    def test_group_by_avg(self, db):
        """Test GROUP BY with AVG."""
        results = db.query('SELECT category, AVG(price) FROM sales GROUP BY category')

        assert len(results) == 2
        cat_avgs = {r['category']: r['AVG(price)'] for r in results}
        # Category A: (9.99 + 19.99 + 19.99) / 3 = 16.66
        # Category B: (4.99 + 9.99 + 4.99) / 3 = 6.66
        assert abs(cat_avgs['A'] - 16.66) < 0.01
        assert abs(cat_avgs['B'] - 6.66) < 0.01

    def test_group_by_multiple_aggregates(self, db):
        """Test GROUP BY with multiple aggregate functions."""
        results = db.query("""
            SELECT category, COUNT(*), SUM(quantity), MIN(price), MAX(price)
            FROM sales GROUP BY category
        """)

        assert len(results) == 2

        for r in results:
            if r['category'] == 'A':
                assert r['COUNT(*)'] == 3
                assert r['SUM(quantity)'] == 23
                assert r['MIN(price)'] == 9.99
                assert r['MAX(price)'] == 19.99
            else:
                assert r['category'] == 'B'
                assert r['COUNT(*)'] == 3
                assert r['SUM(quantity)'] == 47
                assert r['MIN(price)'] == 4.99
                assert r['MAX(price)'] == 9.99

    def test_group_by_with_where(self, db):
        """Test GROUP BY combined with WHERE."""
        results = db.query("""
            SELECT category, SUM(quantity)
            FROM sales
            WHERE quantity > 10
            GROUP BY category
        """)

        # Only category 'B' has rows with quantity > 10
        # id=3: quantity=20 (B), id=4: quantity=15 (B), id=6: quantity=12 (B)
        assert len(results) == 1
        assert results[0]['category'] == 'B'
        assert results[0]['SUM(quantity)'] == 47  # 20+15+12

    def test_aggregate_with_where(self, db):
        """Test aggregate function with WHERE clause."""
        results = db.query("SELECT SUM(quantity) FROM sales WHERE category = 'A'")

        assert len(results) == 1
        assert results[0]['SUM(quantity)'] == 23  # 10+5+8
