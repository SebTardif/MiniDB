"""Tests for WHERE, ORDER BY, GROUP BY queries."""

import os
import tempfile

import pytest

from minidb_sql import Column, ColumnType, MiniDB
from minidb_sql.errors import ColumnError, ColumnNotFoundError, InvalidQueryError, SyntaxError_, TypeMismatchError


class TestParserErrors:
    """Tests for SQL parsing error paths."""

    def test_syntax_error_unexpected_token(self):
        """Test that malformed SQL raises SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('SELECTX * FROM users')

    def test_syntax_error_unterminated_string(self):
        """Test that an unterminated string literal raises SyntaxError_."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(SyntaxError_, match='Unterminated string'):
            db.execute("INSERT INTO t (id, v) VALUES (1, 'hello)")

    def test_syntax_error_unexpected_character(self):
        """Test that unexpected characters raise SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('SELECT * FROM t WHERE id @ 1')

    def test_empty_sql(self):
        """Test that empty SQL raises SyntaxError_."""
        db = MiniDB()
        with pytest.raises(SyntaxError_):
            db.execute('')

    def test_sql_comments_are_skipped(self):
        """Line and block comments match the README examples."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name STRING, n INTEGER)')
        db.execute("INSERT INTO t (id, name, n) VALUES (1, 'a', -3)")
        assert db.query("SELECT name FROM t WHERE name = 'a' -- tail") == [{'name': 'a'}]
        assert db.query('SELECT name FROM t /* mid */ WHERE id = 1') == [{'name': 'a'}]
        assert db.query('SELECT n FROM t WHERE n = -3') == [{'n': -3}]
        with pytest.raises(SyntaxError_, match='Unterminated block comment'):
            db.query('SELECT name FROM t /* oops WHERE id = 1')

    def test_where_parentheses_have_a_depth_limit(self):
        """Hundreds of nested WHERE parentheses raise SyntaxError_, not RecursionError."""
        db = MiniDB()
        db.execute('CREATE TABLE t (n INTEGER)')
        db.execute('INSERT INTO t (n) VALUES (1)')
        modest = 'SELECT n FROM t WHERE ' + ('(' * 8) + 'n = 1' + (')' * 8)
        assert db.query(modest) == [{'n': 1}]
        deep = 'SELECT n FROM t WHERE ' + ('(' * 101) + 'n = 1' + (')' * 101)
        with pytest.raises(SyntaxError_, match='Parentheses nested more than 100 levels'):
            db.query(deep)

    def test_having_after_select_is_rejected(self):
        """HAVING without GROUP BY or SELECT aggregates raises InvalidQueryError."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'Alice')")
        with pytest.raises(InvalidQueryError):
            db.query('SELECT * FROM users HAVING COUNT(*) > 1')

    def test_offset_after_select_is_rejected(self):
        """OFFSET is leftover syntax and must raise SyntaxError_."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        with pytest.raises(SyntaxError_):
            db.query('SELECT * FROM users OFFSET 1')

    def test_optional_semicolon_still_works(self):
        """A trailing semicolon is still accepted."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice');")
        results = db.query('SELECT * FROM users;')
        assert len(results) == 1
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'


class TestTypeValidation:
    """Tests for type validation and NULL constraint errors."""

    def test_null_value_on_primary_key(self):
        """Test inserting NULL into a non-nullable primary key column."""
        from minidb_sql.errors import NullValueError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        with pytest.raises(NullValueError):
            db.execute("INSERT INTO t (id, v) VALUES (NULL, 'hello')")

    def test_insert_with_missing_nullable_column(self):
        """Test that missing nullable columns default to NULL."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v STRING)')
        db.execute('INSERT INTO t (id) VALUES (1)')
        results = db.query('SELECT * FROM t WHERE id = 1')
        assert len(results) == 1
        assert results[0]['v'] is None

    def test_duplicate_primary_key_error_message(self):
        """Test that DuplicateKeyError includes the key value."""
        from minidb_sql.errors import DuplicateKeyError

        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO t (id) VALUES (42)')
        with pytest.raises(DuplicateKeyError) as exc_info:
            db.execute('INSERT INTO t (id) VALUES (42)')
        assert '42' in str(exc_info.value)

    def test_insert_type_mismatch(self):
        """INSERT of a non-castable value raises TypeMismatchError."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, age INTEGER)')
        with pytest.raises(TypeMismatchError):
            db.execute("INSERT INTO t (id, age) VALUES (1, 'not-a-number')")
        with pytest.raises(TypeMismatchError):
            db.execute('INSERT INTO t (id, age) VALUES (1, 1.9)')
        db.execute('INSERT INTO t (id, age) VALUES (2, 2.0)')
        assert db.query('SELECT age FROM t WHERE id = 2') == [{'age': 2}]

    def test_column_default_is_cast_like_insert(self):
        """An omitted column stores the default after the column type's cast.

        INTEGER default '5' used to stay a string, so WHERE n = 5 missed
        the row and loading the saved file raised TypeMismatchError.
        """
        with pytest.raises(TypeMismatchError, match="column 'n'"):
            Column('n', ColumnType.INTEGER, default='nope')

        db = MiniDB()
        db.create_table(
            'd',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('n', ColumnType.INTEGER, default='5'),
                Column('width', ColumnType.INTEGER, default=1.0),
                Column('active', ColumnType.BOOLEAN, default=False),
            ],
        )
        db.execute('INSERT INTO d (id) VALUES (1)')
        assert db.query('SELECT n, width, active FROM d') == [{'n': 5, 'width': 1, 'active': False}]
        assert isinstance(db.query('SELECT n FROM d')[0]['n'], int)
        assert isinstance(db.query('SELECT width FROM d')[0]['width'], int)
        assert db.query('SELECT id FROM d WHERE n = 5') == [{'id': 1}]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as handle:
            filepath = handle.name
        try:
            db.save(filepath)
            loaded = MiniDB.load(filepath)
        finally:
            os.remove(filepath)
        assert loaded.query('SELECT n, width, active FROM d') == [{'n': 5, 'width': 1, 'active': False}]

    def test_create_table_rejects_duplicate_column_names(self):
        """Two columns with one name used to keep the later type.

        CREATE TABLE (name STRING, name INTEGER) stored INSERT '5' as the
        integer 5. A repeated PRIMARY KEY name stored the integer 1 as text.
        """
        db = MiniDB()
        with pytest.raises(ColumnError, match="Duplicate column name 'name'"):
            db.execute('CREATE TABLE u (id INTEGER PRIMARY KEY, name STRING, name INTEGER)')
        with pytest.raises(ColumnError, match="Duplicate column name 'id'"):
            db.execute('CREATE TABLE u (id INTEGER PRIMARY KEY, id STRING)')
        with pytest.raises(ColumnError, match="Duplicate column name 'name'"):
            db.create_table(
                'u',
                [
                    Column('id', ColumnType.INTEGER, primary_key=True),
                    Column('name', ColumnType.STRING),
                    Column('name', ColumnType.INTEGER),
                ],
            )
        db.execute('CREATE TABLE u (id INTEGER PRIMARY KEY, name STRING)')
        assert 'u' in db

    def test_boolean_rejects_non_booleans(self):
        """A BOOLEAN column does not treat 'bob' as false or 2 as true."""
        db = MiniDB()
        db.execute('CREATE TABLE flags (id INTEGER PRIMARY KEY, f BOOLEAN)')
        with pytest.raises(TypeMismatchError):
            db.execute("INSERT INTO flags (id, f) VALUES (1, 'bob')")
        with pytest.raises(TypeMismatchError):
            db.execute('INSERT INTO flags (id, f) VALUES (2, 2)')
        db.execute("INSERT INTO flags (id, f) VALUES (3, 'false')")
        assert db.query('SELECT f FROM flags') == [{'f': False}]

    def test_integer_does_not_equal_boolean(self):
        """id = true is a type error. Python would treat true as 1."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, active BOOLEAN)')
        db.execute("INSERT INTO users (id, name, active) VALUES (1, 'Alice', true)")
        db.execute("INSERT INTO users (id, name, active) VALUES (0, 'Zero', false)")
        with pytest.raises(TypeMismatchError):
            db.query('SELECT name FROM users WHERE id = true')
        with pytest.raises(TypeMismatchError):
            db.query('SELECT name FROM users WHERE active = 1')

    def test_duplicate_select_alias_is_rejected(self):
        """Two outputs named label do not drop the first value."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        with pytest.raises(InvalidQueryError, match='label'):
            db.query('SELECT name AS label, age AS label FROM users')

    def test_update_type_mismatch(self):
        """UPDATE of a non-castable value raises TypeMismatchError."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, age INTEGER)')
        db.execute('INSERT INTO t (id, age) VALUES (1, 30)')
        with pytest.raises(TypeMismatchError):
            db.execute("UPDATE t SET age = 'not-a-number' WHERE id = 1")
        results = db.query('SELECT age FROM t WHERE id = 1')
        assert results[0]['age'] == 30

    def test_where_order_compare_incompatible_types_raises(self):
        """Order comparisons of different types raise TypeMismatchError, not TypeError."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")

        assert 'table_scan' in db.explain('SELECT * FROM users WHERE name > 5')
        with pytest.raises(TypeMismatchError, match=r"column 'name'"):
            db.query('SELECT * FROM users WHERE name > 5')

        assert 'table_scan' in db.explain("SELECT * FROM users WHERE age > 'x'")
        with pytest.raises(TypeMismatchError, match=r"column 'age'"):
            db.query("SELECT * FROM users WHERE age > 'x'")

        with pytest.raises(TypeMismatchError, match=r"column 'name'"):
            db.query('SELECT * FROM users WHERE name < 5')
        with pytest.raises(TypeMismatchError, match=r"column 'age'"):
            db.query("SELECT * FROM users WHERE age <= 'x'")

    def test_where_order_compare_on_primary_key_index_raises(self):
        """Range lookup on an INTEGER primary key rejects a string bound."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")

        assert 'index_range_scan' in db.explain("SELECT * FROM users WHERE id > 'x'")
        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            db.query("SELECT * FROM users WHERE id > 'x'")
        with pytest.raises(TypeMismatchError, match=r"column 'id'"):
            db.query("SELECT * FROM users WHERE id <= 'x'")

    def test_where_equality_different_types_is_false(self):
        """Equality of different types stays false and does not raise."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")

        assert db.query('SELECT * FROM users WHERE name = 5') == []
        assert db.query("SELECT * FROM users WHERE age = 'x'") == []
        assert db.query("SELECT * FROM users WHERE id = 'x'") == []

    def test_where_null_order_compare_is_false(self):
        """NULL compared with an order operator stays false, not an error."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute('INSERT INTO users (id) VALUES (1)')

        assert db.query("SELECT * FROM users WHERE name > 'a'") == []
        assert db.query('SELECT * FROM users WHERE age >= 1') == []
        assert db.query('SELECT * FROM users WHERE name < 5') == []


class TestUnknownColumns:
    """Unknown column names must raise ColumnNotFoundError."""

    @pytest.fixture
    def db(self):
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
        return db

    def test_select_unknown_column(self, db):
        """SELECT of a missing column raises ColumnNotFoundError."""
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT missing FROM users')

    def test_where_unknown_column(self, db):
        """WHERE on a missing column raises ColumnNotFoundError."""
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT * FROM users WHERE ghost = 1')

    def test_update_unknown_column(self, db):
        """UPDATE of a missing column raises ColumnNotFoundError."""
        with pytest.raises(ColumnNotFoundError):
            db.execute('UPDATE users SET ghost = 1')
        results = db.query('SELECT id, name FROM users ORDER BY id')
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'
        assert results[1]['id'] == 2
        assert results[1]['name'] == 'Bob'

    def test_select_star_still_works(self, db):
        """SELECT * still returns every unprefixed column."""
        results = db.query('SELECT * FROM users ORDER BY id')
        assert len(results) == 2
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'
        assert results[1]['id'] == 2
        assert results[1]['name'] == 'Bob'

    def test_select_qualified_column_single_table(self, db):
        """Qualified users.id on a single-table scan falls back to the unprefixed key."""
        results = db.query('SELECT users.id, users.name FROM users WHERE users.id = 1')
        assert len(results) == 1
        assert results[0]['id'] == 1
        assert results[0]['name'] == 'Alice'

    def test_unknown_qualifier_does_not_read_the_bare_column(self, db):
        """missing.name is not users.name, in WHERE, SELECT, or ORDER BY."""
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT id FROM users WHERE missing.name = 'Alice'")
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT missing.name FROM users')
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT * FROM users ORDER BY missing.name')
        with pytest.raises(ColumnNotFoundError):
            db.execute("UPDATE users SET name = 'Zed' WHERE missing.name = 'Alice'")

        ordered = db.query('SELECT name FROM users ORDER BY users.name')
        assert [row['name'] for row in ordered] == ['Alice', 'Bob']
        assert db.query("SELECT name FROM users WHERE users.name = 'Alice'")[0]['name'] == 'Alice'

    def test_qualifier_from_another_table_is_unknown(self, db):
        """orders.name is unknown when orders is not part of this query."""
        db.create_table(
            'orders',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
            ],
        )
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT id FROM users WHERE orders.name = 'Alice'")

    def test_left_join_null_right_column_is_not_unknown(self, db):
        """A NULL right-side column after LEFT JOIN is present, not missing."""
        db.create_table(
            'orders',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('user_id', ColumnType.INTEGER),
                Column('product', ColumnType.STRING),
            ],
        )
        db.execute("INSERT INTO orders (id, user_id, product) VALUES (1, 1, 'Widget')")

        results = db.query("""
            SELECT users.name, orders.product
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
        """)
        by_name = {r['name']: r['product'] for r in results}
        assert by_name['Alice'] == 'Widget'
        assert by_name['Bob'] is None

        matched = db.query("""
            SELECT users.name
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
            WHERE orders.product = 'Widget'
        """)
        assert [r['name'] for r in matched] == ['Alice']

        with pytest.raises(ColumnNotFoundError):
            db.query("""
                SELECT users.name
                FROM users
                LEFT JOIN orders ON users.id = orders.user_id
                WHERE orders.name = 'Alice'
            """)
        with pytest.raises(ColumnNotFoundError):
            db.query("""
                SELECT users.name
                FROM users
                LEFT JOIN orders ON users.id = orders.user_id
                WHERE missing.product = 'Widget'
            """)
        with pytest.raises(ColumnNotFoundError):
            db.query("""
                SELECT users.name
                FROM users
                LEFT JOIN orders ON users.id = orders.user_id
                ORDER BY orders.name
            """)
        with pytest.raises(ColumnNotFoundError):
            db.query("""
                SELECT users.name, COUNT(*) AS n
                FROM users
                JOIN orders ON users.id = orders.user_id
                GROUP BY name
                HAVING orders.name = 'Alice'
            """)

    def test_empty_table_unknown_qualifier_is_still_an_error(self):
        """SELECT missing.name on an empty table is still an unknown column."""
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT missing.name FROM users')


class TestIndexedPredicate:
    """An earlier non-index predicate must not empty an index probe."""

    def test_leading_like_in_and_not_equal_keep_the_indexed_row(self):
        """LIKE, IN, and != before = or >= still return the matching primary key."""
        db = MiniDB()
        db.execute('CREATE TABLE t (name STRING PRIMARY KEY)')
        db.execute("INSERT INTO t (name) VALUES ('Alice')")
        db.execute("INSERT INTO t (name) VALUES ('Bob')")

        like_and_range = db.query("SELECT name FROM t WHERE name LIKE 'A%' AND name >= 'A' ORDER BY name")
        assert [row['name'] for row in like_and_range] == ['Alice']

        not_equal = db.query("SELECT name FROM t WHERE name != 'nope' AND name = 'Alice'")
        assert [row['name'] for row in not_equal] == ['Alice']

        in_list = db.query("SELECT name FROM t WHERE name IN ('Alice') AND name = 'Alice'")
        assert [row['name'] for row in in_list] == ['Alice']

        range_then_like = db.query("SELECT name FROM t WHERE name >= 'A' AND name LIKE 'A%' ORDER BY name")
        assert [row['name'] for row in range_then_like] == ['Alice']

        either = db.query("SELECT name FROM t WHERE (name = 'Bob' OR name = 'Alice') AND name = 'Alice'")
        assert [row['name'] for row in either] == ['Alice']

        ranged = db.query("SELECT name FROM t WHERE (name >= 'Z' OR name = 'Alice') AND name >= 'A'")
        assert [row['name'] for row in ranged] == ['Alice']

    def test_index_miss_still_rejects_an_unknown_column(self):
        """A primary-key miss must not hide a qualifier or column that does not exist."""
        db = MiniDB()
        db.execute('CREATE TABLE t (name STRING PRIMARY KEY)')
        db.execute("INSERT INTO t (name) VALUES ('Alice')")
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT name FROM t WHERE missing.name = 'Zoe'")
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT name FROM t WHERE missing.name = 'Alice'")

        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        with pytest.raises(ColumnNotFoundError):
            db.query('SELECT id FROM users WHERE id = 999 AND ghost = 1')
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT id FROM users WHERE id = 999 AND missing.name = 'Alice'")

    def test_unindexed_like_and_range_still_filters(self):
        """A non-indexed column still applies both LIKE and >=."""
        db = MiniDB()
        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name STRING)')
        db.execute("INSERT INTO t (id, name) VALUES (1, 'Ann')")
        db.execute("INSERT INTO t (id, name) VALUES (2, 'Amy')")
        db.execute("INSERT INTO t (id, name) VALUES (3, 'Bob')")
        rows = db.query("SELECT name FROM t WHERE name LIKE 'A%' AND name >= 'A' ORDER BY name")
        assert [row['name'] for row in rows] == ['Amy', 'Ann']


class TestWhereClause:
    """Tests for WHERE clause operations."""

    @pytest.fixture
    def db(self):
        """Create a populated test database."""
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

        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (1, 'Alice', 30, 50000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (2, 'Bob', 25, 45000.0, false)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (3, 'Charlie', 35, 55000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (4, 'Diana', 28, 48000.0, true)")
        db.execute("INSERT INTO users (id, name, age, salary, active) VALUES (5, 'Eve', 32, 52000.0, false)")

        return db

    def test_where_equality(self, db):
        """Test WHERE with equality comparison."""
        results = db.query('SELECT * FROM users WHERE id = 1')

        assert len(results) == 1
        assert results[0]['name'] == 'Alice'

    def test_where_greater_than(self, db):
        """Test WHERE with greater than comparison."""
        results = db.query('SELECT * FROM users WHERE age > 30')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_less_than(self, db):
        """Test WHERE with less than comparison."""
        results = db.query('SELECT * FROM users WHERE age < 30')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Diana' in names

    def test_where_greater_equal(self, db):
        """Test WHERE with greater than or equal comparison."""
        results = db.query('SELECT * FROM users WHERE age >= 30')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_less_equal(self, db):
        """Test WHERE with less than or equal comparison."""
        results = db.query('SELECT * FROM users WHERE age <= 30')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Bob' in names
        assert 'Diana' in names

    def test_where_and(self, db):
        """Test WHERE with AND condition."""
        results = db.query('SELECT * FROM users WHERE age > 25 AND active = true')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Diana' in names

    def test_where_or(self, db):
        """Test WHERE with OR condition."""
        results = db.query('SELECT * FROM users WHERE age < 26 OR age > 31')

        # Bob (25), Charlie (35), and Eve (32) match
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_and_binds_tighter_than_or(self, db):
        """AND binds tighter than OR: age < 26 OR (age > 32 AND active)."""
        results = db.query('SELECT * FROM users WHERE age < 26 OR age > 32 AND active = true')

        names = {r['name'] for r in results}
        assert names == {'Bob', 'Charlie'}

    def test_where_parentheses(self, db):
        """Parentheses override precedence: (age < 26 OR age > 32) AND active."""
        results = db.query('SELECT * FROM users WHERE (age < 26 OR age > 32) AND active = true')

        names = {r['name'] for r in results}
        assert names == {'Charlie'}

    def test_where_like_prefix(self, db):
        """Test WHERE with LIKE pattern matching (prefix)."""
        results = db.query("SELECT * FROM users WHERE name LIKE 'A%'")

        assert len(results) == 1
        assert results[0]['name'] == 'Alice'

    def test_where_like_suffix(self, db):
        """Test WHERE with LIKE pattern matching (suffix)."""
        results = db.query("SELECT * FROM users WHERE name LIKE '%e'")

        # Alice, Charlie, and Eve all end with 'e'
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_like_contains(self, db):
        """Test WHERE with LIKE pattern matching (contains)."""
        results = db.query("SELECT * FROM users WHERE name LIKE '%a%'")

        # Alice, Charlie, and Diana all contain 'a' (case-insensitive)
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Diana' in names

    def test_where_in(self, db):
        """Test WHERE with IN clause."""
        results = db.query('SELECT * FROM users WHERE id IN (1, 3, 5)')

        assert len(results) == 3
        names = {r['name'] for r in results}
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Eve' in names

    def test_where_not_equals(self, db):
        """Test WHERE with not equals comparison."""
        results = db.query('SELECT * FROM users WHERE active != true')

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert 'Bob' in names
        assert 'Eve' in names

    def test_where_not_boolean(self, db):
        """NOT inverts a boolean equality."""
        results = db.query('SELECT * FROM users WHERE NOT active = true')

        names = {r['name'] for r in results}
        assert names == {'Bob', 'Eve'}

    def test_where_not_comparison(self, db):
        """NOT age > 30 matches ages that are not greater than 30."""
        results = db.query('SELECT * FROM users WHERE NOT age > 30')

        names = {r['name'] for r in results}
        assert names == {'Alice', 'Bob', 'Diana'}

    def test_where_not_primary_key(self, db):
        """NOT on a PK must not plan the un-negated index lookup."""
        results = db.query('SELECT name FROM users WHERE NOT id = 1')
        names = {r['name'] for r in results}
        assert names == {'Bob', 'Charlie', 'Diana', 'Eve'}

        results = db.query('SELECT name FROM users WHERE NOT id > 1')
        names = {r['name'] for r in results}
        assert names == {'Alice'}

    def test_where_is_null(self):
        """WHERE age IS NULL matches a nullable missing age."""
        db = MiniDB()
        db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO people (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO people (id, name) VALUES (2, 'Bob')")
        results = db.query('SELECT name FROM people WHERE age IS NULL')
        assert [r['name'] for r in results] == ['Bob']

    def test_where_is_not_null(self):
        """WHERE age IS NOT NULL excludes the missing age."""
        db = MiniDB()
        db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO people (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO people (id, name) VALUES (2, 'Bob')")
        results = db.query('SELECT name FROM people WHERE age IS NOT NULL')
        assert [r['name'] for r in results] == ['Alice']

    def test_where_not_is_null_inverts(self):
        """NOT age IS NULL inverts the IS NULL predicate."""
        db = MiniDB()
        db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO people (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO people (id, name) VALUES (2, 'Bob')")
        results = db.query('SELECT name FROM people WHERE NOT age IS NULL')
        assert [r['name'] for r in results] == ['Alice']

    def test_comparison_with_null_matches_nothing(self):
        """A comparison with NULL is unknown, so WHERE keeps no row."""
        db = MiniDB()
        db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY, name STRING, age INTEGER)')
        db.execute("INSERT INTO people (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO people (id, name) VALUES (2, 'Bob')")

        assert db.query('SELECT name FROM people WHERE age = NULL') == []
        assert db.query('SELECT name FROM people WHERE age != NULL') == []
        assert db.query('SELECT name FROM people WHERE NOT age = NULL') == []
        assert db.query('SELECT name FROM people WHERE age > NULL') == []
        assert db.query('SELECT name FROM people WHERE name LIKE NULL') == []
        assert db.query('SELECT name FROM people WHERE NOT age IS NULL') == [{'name': 'Alice'}]

        plan = db.explain('SELECT name FROM people WHERE id > NULL')
        assert 'index_range_scan' not in plan
        assert 'index_scan' not in plan

    def test_order_by_asc(self, db):
        """Test ORDER BY ascending."""
        results = db.query('SELECT * FROM users ORDER BY age ASC')

        ages = [r['age'] for r in results]
        assert ages == [25, 28, 30, 32, 35]

    def test_order_by_desc(self, db):
        """Test ORDER BY descending."""
        results = db.query('SELECT * FROM users ORDER BY salary DESC')

        salaries = [r['salary'] for r in results]
        assert salaries == [55000.0, 52000.0, 50000.0, 48000.0, 45000.0]

    def test_order_by_mixed_directions(self, db):
        """Test ORDER BY with mixed ASC/DESC on different columns."""
        # active has true/false, age varies within each group
        results = db.query('SELECT * FROM users ORDER BY active DESC, age ASC')

        # active=true first (DESC), then within each group sorted by age ASC
        active_flags = [r['active'] for r in results]
        assert active_flags == [True, True, True, False, False]

        # Ages within active=true group should be ascending
        active_ages = [r['age'] for r in results if r['active'] is True]
        assert active_ages == sorted(active_ages)

        # Ages within active=false group should be ascending
        inactive_ages = [r['age'] for r in results if r['active'] is False]
        assert inactive_ages == sorted(inactive_ages)

    def test_order_by_with_where(self, db):
        """Test ORDER BY combined with WHERE."""
        results = db.query('SELECT * FROM users WHERE active = true ORDER BY age DESC')

        assert len(results) == 3
        ages = [r['age'] for r in results]
        assert ages == [35, 30, 28]

    def test_limit(self, db):
        """Test LIMIT clause."""
        results = db.query('SELECT * FROM users ORDER BY id LIMIT 2')

        assert len(results) == 2
        assert results[0]['name'] == 'Alice'
        assert results[1]['name'] == 'Bob'

    def test_limit_with_where(self, db):
        """Test LIMIT combined with WHERE."""
        results = db.query('SELECT * FROM users WHERE active = true ORDER BY age ASC LIMIT 1')

        assert len(results) == 1
        assert results[0]['name'] == 'Diana'

    def test_negative_limit_is_rejected(self, db):
        """LIMIT -1 must not drop the last row via a Python slice."""
        with pytest.raises(InvalidQueryError):
            db.query('SELECT * FROM users ORDER BY id LIMIT -1')

    def test_order_by_unprojected_column(self, db):
        """ORDER BY can use a table column that is not in the SELECT list."""
        by_age = db.query('SELECT name FROM users ORDER BY age')
        assert [row['name'] for row in by_age] == ['Bob', 'Diana', 'Alice', 'Eve', 'Charlie']

        by_age_desc = db.query('SELECT id FROM users WHERE age > 30 ORDER BY age DESC')
        assert [row['id'] for row in by_age_desc] == [3, 5]

        aliased = db.query('SELECT age AS years FROM users ORDER BY age')
        assert [row['years'] for row in aliased] == [25, 28, 30, 32, 35]
        assert 'age' not in aliased[0]

    def test_distinct_order_by_must_be_selected(self, db):
        """DISTINCT cannot order by a column the result does not show."""
        with pytest.raises(InvalidQueryError, match='DISTINCT'):
            db.query('SELECT DISTINCT name FROM users ORDER BY age')

    def test_order_by_alias(self, db):
        """ORDER BY can use a SELECT alias as the result key."""
        results = db.query('SELECT name AS n FROM users ORDER BY n')

        assert [r['n'] for r in results] == ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']

    def test_select_column_as_alias(self, db):
        """SELECT name AS n keys the result as n, not name."""
        results = db.query('SELECT name AS n FROM users WHERE id = 1')

        assert len(results) == 1
        assert results[0]['n'] == 'Alice'
        assert 'name' not in results[0]

    def test_select_column_implicit_alias(self, db):
        """SELECT name n also keys the result as n."""
        results = db.query('SELECT name n FROM users WHERE id = 1')

        assert len(results) == 1
        assert results[0]['n'] == 'Alice'
        assert 'name' not in results[0]

    def test_select_count_as_alias(self, db):
        """SELECT COUNT(*) AS cnt keys the aggregate as cnt."""
        results = db.query('SELECT COUNT(*) AS cnt FROM users')

        assert len(results) == 1
        assert results[0]['cnt'] == 5
        assert 'COUNT(*)' not in results[0]

    def test_select_unaliased_columns(self, db):
        """Unaliased SELECT still uses the column names."""
        results = db.query('SELECT name, age FROM users WHERE id = 1')

        assert len(results) == 1
        assert results[0]['name'] == 'Alice'
        assert results[0]['age'] == 30


class TestDistinct:
    """Tests for SELECT DISTINCT."""

    @pytest.fixture
    def db(self):
        """Two Alices and one Bob (same name/age projection for the Alices)."""
        db = MiniDB()
        db.create_table(
            'users',
            [
                Column('id', ColumnType.INTEGER, primary_key=True),
                Column('name', ColumnType.STRING),
                Column('age', ColumnType.INTEGER),
            ],
        )
        db.execute("INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (2, 'Alice', 30)")
        db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Bob', 25)")
        return db

    def test_select_distinct_name(self, db):
        """SELECT DISTINCT name drops the duplicate Alice."""
        results = db.query('SELECT DISTINCT name FROM users')
        assert [r['name'] for r in results] == ['Alice', 'Bob']

    def test_select_distinct_star_same_projection(self, db):
        """PK blocks identical full rows; DISTINCT on the shared name/age projection."""
        results = db.query('SELECT DISTINCT name, age FROM users')
        assert len(results) == 2
        assert results[0] == {'name': 'Alice', 'age': 30}
        assert results[1] == {'name': 'Bob', 'age': 25}

    def test_select_distinct_star_identical_rows(self):
        """SELECT DISTINCT * after two identical inserts (no PK)."""
        db = MiniDB()
        db.execute('CREATE TABLE dupes (name STRING, age INTEGER)')
        db.execute("INSERT INTO dupes (name, age) VALUES ('Alice', 30)")
        db.execute("INSERT INTO dupes (name, age) VALUES ('Alice', 30)")
        results = db.query('SELECT DISTINCT * FROM dupes')
        assert results == [{'name': 'Alice', 'age': 30}]

    def test_select_without_distinct_keeps_duplicates(self, db):
        """SELECT name without DISTINCT still returns both Alices."""
        results = db.query('SELECT name FROM users')
        assert [r['name'] for r in results] == ['Alice', 'Alice', 'Bob']

    def test_select_distinct_limit_1(self, db):
        """DISTINCT + LIMIT 1 returns one unique row."""
        results = db.query('SELECT DISTINCT name FROM users LIMIT 1')
        assert len(results) == 1
        assert results[0]['name'] == 'Alice'


class TestCaseExpression:
    """Searched CASE in the select list. WHEN uses WHERE comparison rules."""

    def _db(self) -> MiniDB:
        db = MiniDB()
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name STRING, age INTEGER, active BOOLEAN)')
        db.execute("INSERT INTO users (id, name, age, active) VALUES (1, 'Ada', 17, true)")
        db.execute("INSERT INTO users (id, name, age, active) VALUES (2, 'Grace', 18, false)")
        db.execute("INSERT INTO users (id, name, age) VALUES (3, 'Lin', NULL)")
        return db

    def test_issue_example_returns_one_value_per_row(self):
        """SELECT CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END."""
        db = self._db()
        rows = db.query("SELECT CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END FROM users ORDER BY id")
        # NULL >= 18 is unknown, so the ELSE arm runs.
        assert rows == [{'CASE': 'minor'}, {'CASE': 'adult'}, {'CASE': 'minor'}]

    def test_first_matching_when_wins_and_alias(self):
        db = self._db()
        sql = (
            "SELECT CASE WHEN age >= 18 THEN 'adult' WHEN age >= 13 THEN 'teen' "
            "ELSE 'child' END AS kind FROM users ORDER BY id"
        )
        assert db.query(sql) == [{'kind': 'teen'}, {'kind': 'adult'}, {'kind': 'child'}]

    def test_missing_else_is_null(self):
        db = self._db()
        rows = db.query("SELECT CASE WHEN age >= 18 THEN 'adult' END AS kind FROM users ORDER BY id")
        assert rows == [{'kind': None}, {'kind': 'adult'}, {'kind': None}]

    def test_is_null_and_else_column(self):
        db = self._db()
        sql = "SELECT CASE WHEN age IS NULL THEN 'missing' ELSE name END AS label FROM users ORDER BY id"
        assert db.query(sql) == [{'label': 'Ada'}, {'label': 'Grace'}, {'label': 'missing'}]

    def test_null_comparison_does_not_match(self):
        db = self._db()
        rows = db.query("SELECT CASE WHEN age = NULL THEN 'yes' ELSE 'no' END AS label FROM users")
        assert rows == [{'label': 'no'}, {'label': 'no'}, {'label': 'no'}]

    def test_boolean_comparison_matches_where(self):
        db = self._db()
        with pytest.raises(TypeMismatchError):
            db.query("SELECT CASE WHEN active = 1 THEN 'yes' ELSE 'no' END FROM users")
        with pytest.raises(TypeMismatchError):
            db.query("SELECT CASE WHEN id = true THEN 'yes' ELSE 'no' END FROM users")

    def test_string_compared_with_int_does_not_match(self):
        """name = 5 is false in WHERE, not a type error. CASE must agree."""
        db = self._db()
        rows = db.query("SELECT CASE WHEN name = 5 THEN 'num' ELSE name END AS label FROM users ORDER BY id")
        assert [row['label'] for row in rows] == ['Ada', 'Grace', 'Lin']

    def test_and_inside_when(self):
        db = self._db()
        db.execute("INSERT INTO users (id, name, age, active) VALUES (4, 'Mae', 40, true)")
        sql = "SELECT CASE WHEN age >= 18 AND active = true THEN 'yes' ELSE 'no' END AS label FROM users ORDER BY id"
        assert db.query(sql) == [
            {'label': 'no'},
            {'label': 'no'},
            {'label': 'no'},
            {'label': 'yes'},
        ]

    def test_grouped_case_uses_the_group_key(self):
        db = self._db()
        sql = (
            "SELECT age, CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END AS kind FROM users GROUP BY age ORDER BY age"
        )
        assert db.query(sql) == [
            {'age': 17, 'kind': 'minor'},
            {'age': 18, 'kind': 'adult'},
            {'age': None, 'kind': 'minor'},
        ]

    def test_ungrouped_case_column_is_rejected(self):
        db = self._db()
        with pytest.raises(InvalidQueryError, match='name'):
            db.query("SELECT CASE WHEN name = 'Ada' THEN 'a' ELSE 'b' END AS kind FROM users GROUP BY age")

    def test_case_with_aggregate_requires_group_by(self):
        db = self._db()
        with pytest.raises(InvalidQueryError, match='age'):
            db.query("SELECT CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END, COUNT(*) FROM users")

    def test_having_can_see_the_case_alias(self):
        db = self._db()
        sql = (
            "SELECT age, CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END AS kind "
            "FROM users GROUP BY age HAVING kind = 'adult'"
        )
        assert db.query(sql) == [{'age': 18, 'kind': 'adult'}]

    def test_order_by_alias(self):
        db = self._db()
        sql = "SELECT CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END AS kind FROM users ORDER BY kind, id"
        assert [row['kind'] for row in db.query(sql)] == ['adult', 'minor', 'minor']

    def test_distinct_collapses_equal_results(self):
        db = self._db()
        rows = db.query("SELECT DISTINCT CASE WHEN age >= 18 THEN 'adult' ELSE 'minor' END AS kind FROM users")
        assert rows == [{'kind': 'minor'}, {'kind': 'adult'}]

    def test_placeholder_binds_left_to_right(self):
        db = self._db()
        sql = "SELECT CASE WHEN age >= ? THEN ? ELSE 'minor' END AS kind FROM users WHERE id = ? "
        assert db.query(sql, [18, 'adult', 2]) == [{'kind': 'adult'}]

    def test_unknown_column_and_syntax(self):
        db = self._db()
        with pytest.raises(ColumnNotFoundError):
            db.query("SELECT CASE WHEN missing = 1 THEN 'a' ELSE 'b' END FROM users")
        with pytest.raises(SyntaxError_, match='END'):
            db.query("SELECT CASE WHEN age >= 18 THEN 'adult' FROM users")
        with pytest.raises(SyntaxError_, match='WHEN'):
            db.query("SELECT CASE age WHEN 18 THEN 'adult' END FROM users")
