"""Tests for JOIN operations."""

import pytest

from minidb import Column, ColumnType, InvalidQueryError, MiniDB, TableNotFoundError


class TestJoins:
    """Tests for JOIN operations."""

    def test_order_by_the_other_tables_same_column_name(self):
        """ORDER BY prefs.name uses prefs.name, not the selected users.name."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute('CREATE TABLE prefs (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'zoe')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'amy')")
        db.execute("INSERT INTO prefs (id, name) VALUES (1, 'ann')")
        db.execute("INSERT INTO prefs (id, name) VALUES (2, 'bob')")
        rows = db.query('SELECT users.name FROM users JOIN prefs ON users.id = prefs.id ORDER BY prefs.name')
        assert [row['name'] for row in rows] == ['zoe', 'amy']

    @pytest.fixture
    def db(self):
        """Create a test database with users and orders tables."""
        db = MiniDB()

        # Users table
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
                Column('email', ColumnType.STRING),
            ],
        )

        db.execute("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')")
        db.execute("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')")
        db.execute("INSERT INTO users (id, name, email) VALUES (3, 'Charlie', 'charlie@example.com')")

        # Orders table
        db.create_table(
            'orders',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('user_id', ColumnType.INTEGER),
                Column('product', ColumnType.STRING),
                Column('total', ColumnType.FLOAT),
            ],
        )

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

    def test_left_join_includes_unmatched(self, db):
        """LEFT JOIN keeps unmatched left rows with NULL right columns."""
        results = db.query("""
            SELECT users.id, users.name, orders.product
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
        """)

        assert len(results) == 6  # 5 matched orders plus Charlie

        charlie = [r for r in results if r['name'] == 'Charlie']
        assert len(charlie) == 1
        assert charlie[0]['id'] == 3
        assert charlie[0]['product'] is None

        alice = [r for r in results if r['name'] == 'Alice']
        assert len(alice) == 2
        assert {r['product'] for r in alice} == {'Widget', 'Gadget'}

    def test_same_column_name_from_both_tables_stays_distinct(self, db):
        """users.id and orders.id must not overwrite each other."""
        results = db.query("""
            SELECT users.id, orders.id
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
        """)

        gadget = [r for r in results if r.get('orders.id') == 2]
        assert len(gadget) == 1
        assert gadget[0]['users.id'] == 1

        charlie = [r for r in results if r.get('users.id') == 3]
        assert len(charlie) == 1
        assert charlie[0]['orders.id'] is None

    def test_left_join_is_null(self, db):
        """Charlie's unmatched LEFT JOIN row matches orders.product IS NULL."""
        results = db.query("""
            SELECT users.name
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
            WHERE orders.product IS NULL
        """)
        assert [r['name'] for r in results] == ['Charlie']

    def test_left_join_is_not_null(self, db):
        """Alice's matched LEFT JOIN rows match orders.product IS NOT NULL."""
        results = db.query("""
            SELECT users.name, orders.product
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
            WHERE orders.product IS NOT NULL
        """)
        assert len(results) == 5
        assert {r['name'] for r in results} == {'Alice', 'Bob'}
        alice = [r for r in results if r['name'] == 'Alice']
        assert len(alice) == 2
        assert all(r['product'] is not None for r in results)

    def test_left_join_preserves_left_pk(self, db):
        """LEFT JOIN must not overwrite the left table primary key with NULL."""
        results = db.query("""
            SELECT users.id, users.name
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
        """)

        assert len(results) == 6
        charlie = [r for r in results if r['name'] == 'Charlie']
        assert len(charlie) == 1
        assert charlie[0]['id'] == 3
        assert charlie[0]['id'] is not None

        ids_by_name = {}
        for row in results:
            ids_by_name.setdefault(row['name'], set()).add(row['id'])
        assert ids_by_name['Alice'] == {1}
        assert ids_by_name['Bob'] == {2}
        assert ids_by_name['Charlie'] == {3}

    def test_join_unknown_table(self, db):
        """JOIN against a missing table raises TableNotFoundError."""
        with pytest.raises(TableNotFoundError):
            db.query('SELECT * FROM users JOIN ghost ON users.id = ghost.user_id')

    def test_join_unknown_on_column(self, db):
        """JOIN ON a missing column raises ColumnNotFoundError."""
        from minidb.errors import ColumnNotFoundError

        with pytest.raises(ColumnNotFoundError):
            db.query("""
                SELECT users.name
                FROM users
                JOIN orders ON users.id = orders.ghost
            """)

    def test_join_reversed_qualifiers(self, db):
        """ON orders.user_id = users.id matches the same 5 rows as the usual order."""
        usual = db.query("""
            SELECT users.name, orders.product, orders.total
            FROM users
            JOIN orders ON users.id = orders.user_id
        """)
        reversed_on = db.query("""
            SELECT users.name, orders.product, orders.total
            FROM users
            JOIN orders ON orders.user_id = users.id
        """)

        assert len(usual) == 5
        assert len(reversed_on) == 5

        usual_pairs = sorted((r['name'], r['product'], r['total']) for r in usual)
        reversed_pairs = sorted((r['name'], r['product'], r['total']) for r in reversed_on)
        assert reversed_pairs == usual_pairs

        names = {r['name'] for r in reversed_on}
        assert names == {'Alice', 'Bob'}

    def test_left_join_reversed_qualifiers_includes_unmatched(self, db):
        """LEFT JOIN with reversed ON qualifiers still includes Charlie."""
        results = db.query("""
            SELECT users.id, users.name, orders.product
            FROM users
            LEFT JOIN orders ON orders.user_id = users.id
        """)

        assert len(results) == 6
        charlie = [r for r in results if r['name'] == 'Charlie']
        assert len(charlie) == 1
        assert charlie[0]['id'] == 3
        assert charlie[0]['product'] is None

        alice = [r for r in results if r['name'] == 'Alice']
        assert len(alice) == 2

    def test_join_unknown_qualifier(self, db):
        """ON ghost.id = users.id raises InvalidQueryError."""
        with pytest.raises(InvalidQueryError, match='ghost'):
            db.query("""
                SELECT users.name
                FROM users
                JOIN orders ON ghost.id = users.id
            """)

    def test_join_unqualified_on_keeps_operand_order(self, db):
        """Unqualified ON uses first operand as FROM side and second as JOIN side."""
        results = db.query("""
            SELECT users.name, orders.product
            FROM users
            JOIN orders ON id = user_id
        """)
        assert len(results) == 5
        names = {r['name'] for r in results}
        assert names == {'Alice', 'Bob'}

    def test_qualified_aggregate_uses_the_named_table(self):
        """COUNT and SUM on a join read the qualified column, not the left bare name."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total INTEGER)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        db.execute("INSERT INTO users (id, name) VALUES (3, 'Zero')")
        db.execute('INSERT INTO orders (id, user_id, total) VALUES (10, 1, 20)')
        db.execute('INSERT INTO orders (id, user_id, total) VALUES (11, 1, 5)')
        rows = db.query(
            'SELECT users.name, COUNT(orders.id) AS n '
            'FROM users LEFT JOIN orders ON users.id = orders.user_id '
            'GROUP BY name ORDER BY name'
        )
        assert [(row['name'], row['n']) for row in rows] == [('Alice', 2), ('Bob', 0), ('Zero', 0)]

        db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY, name STRING, total INTEGER)')
        db.execute("INSERT INTO people (id, name, total) VALUES (1, 'Alice', 1000)")
        db.execute("INSERT INTO people (id, name, total) VALUES (2, 'Bob', 2000)")
        summed = db.query(
            'SELECT people.name, SUM(orders.total) AS s '
            'FROM people JOIN orders ON people.id = orders.user_id '
            'GROUP BY name ORDER BY name'
        )
        assert [(row['name'], row['s']) for row in summed] == [('Alice', 25)]

    def test_group_by_qualified_id_uses_that_table(self):
        """GROUP BY orders.id does not bucket rows by users.id."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        db.execute('INSERT INTO orders (id, user_id) VALUES (10, 1)')
        db.execute('INSERT INTO orders (id, user_id) VALUES (11, 1)')
        db.execute('INSERT INTO orders (id, user_id) VALUES (12, 2)')
        rows = db.query(
            'SELECT orders.id, COUNT(*) AS n FROM users '
            'JOIN orders ON users.id = orders.user_id GROUP BY orders.id ORDER BY id'
        )
        assert [row['id'] for row in rows] == [10, 11, 12]
        assert 'orders.id' not in rows[0]
        with pytest.raises(InvalidQueryError, match='ambiguous'):
            db.query('SELECT orders.id, COUNT(*) AS n FROM users JOIN orders ON users.id = orders.user_id GROUP BY id')

    def test_star_of_one_table_omits_the_other(self):
        """SELECT users.* does not return order columns, and orders.* keeps the order id."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, product STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO orders (id, user_id, product) VALUES (10, 1, 'Book')")
        users = db.query('SELECT users.* FROM users JOIN orders ON users.id = orders.user_id WHERE orders.id = 10')
        assert users == [{'id': 1, 'name': 'Alice'}]
        orders = db.query('SELECT orders.* FROM users JOIN orders ON users.id = orders.user_id WHERE orders.id = 10')
        assert orders == [{'id': 10, 'user_id': 1, 'product': 'Book'}]

    def test_second_join_can_name_the_middle_table(self):
        """A later ON clause can still read the middle table."""
        db = MiniDB()
        db.execute('CREATE TABLE a (id INTEGER PRIMARY KEY)')
        db.execute('CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER)')
        db.execute('CREATE TABLE c (b_id INTEGER, label STRING)')
        db.execute('INSERT INTO a (id) VALUES (1)')
        db.execute('INSERT INTO b (id, a_id) VALUES (10, 1)')
        db.execute("INSERT INTO c (b_id, label) VALUES (10, 'via-b')")
        db.execute("INSERT INTO c (b_id, label) VALUES (1, 'via-a')")
        rows = db.query('SELECT c.label FROM a JOIN b ON a.id = b.a_id JOIN c ON b.id = c.b_id')
        assert rows == [{'label': 'via-b'}]
        with pytest.raises(InvalidQueryError, match='ambiguous'):
            db.query('SELECT c.label FROM a JOIN b ON a.id = b.a_id JOIN c ON id = b_id')

    def test_right_join_not_supported(self, db):
        """RIGHT JOIN raises; INNER and LEFT JOIN still work."""
        with pytest.raises(InvalidQueryError, match='RIGHT JOIN is not supported'):
            db.query("""
                SELECT users.name, orders.product
                FROM users
                RIGHT JOIN orders ON users.id = orders.user_id
            """)

        inner = db.query("""
            SELECT users.name, orders.product
            FROM users
            JOIN orders ON users.id = orders.user_id
        """)
        assert len(inner) == 5

        left = db.query("""
            SELECT users.name, orders.product
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
        """)
        assert len(left) == 6
