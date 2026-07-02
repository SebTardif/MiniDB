#!/usr/bin/env python3
"""
MiniDB Demo Script

Demonstrates all features of MiniDB including:
- Creating tables
- INSERT, SELECT, UPDATE, DELETE
- WHERE clauses with AND/OR
- ORDER BY, GROUP BY
- Aggregations (COUNT, SUM, AVG, MIN, MAX)
- JOINs
- Persistence
"""

from minidb import MiniDB


def print_section(title: str):
    """Print a section header."""
    print(f'\n{"=" * 60}')
    print(f' {title}')
    print('=' * 60)


def print_results(results, title: str | None = None):
    """Print query results in a formatted way."""
    if title:
        print(f'\n{title}:')
    if not results:
        print('  (no results)')
        return

    # Get column widths
    columns = list(results[0].keys())
    widths = {col: len(col) for col in columns}
    for row in results:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ''))))

    # Print header
    header = ' | '.join(col.ljust(widths[col]) for col in columns)
    print(f'  {header}')
    print(f'  {"-" * len(header)}')

    # Print rows
    for row in results:
        values = ' | '.join(str(row.get(col, '')).ljust(widths[col]) for col in columns)
        print(f'  {values}')


def main():
    """Run the MiniDB demo."""
    print('\n' + '=' * 60)
    print(' MiniDB - Miniature In-Memory Database Demo')
    print('=' * 60)

    # Create database
    print_section('1. Creating Database and Tables')
    db = MiniDB()

    # Create users table
    print("\nCreating 'users' table...")
    db.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name STRING,
            email STRING,
            age INTEGER,
            salary FLOAT,
            active BOOLEAN
        )
    """)
    print("  Table 'users' created successfully!")

    # Create orders table
    print("\nCreating 'orders' table...")
    db.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            product STRING,
            quantity INTEGER,
            total FLOAT
        )
    """)
    print("  Table 'orders' created successfully!")

    # Insert data
    print_section('2. Inserting Data')

    users_data = [
        (1, 'Alice Johnson', 'alice@example.com', 30, 75000.0, True),
        (2, 'Bob Smith', 'bob@example.com', 25, 55000.0, True),
        (3, 'Charlie Brown', 'charlie@example.com', 35, 90000.0, False),
        (4, 'Diana Prince', 'diana@example.com', 28, 65000.0, True),
        (5, 'Eve Wilson', 'eve@example.com', 32, 80000.0, True),
    ]

    print('\nInserting users...')
    for user in users_data:
        db.execute(f"""
            INSERT INTO users (id, name, email, age, salary, active)
            VALUES ({user[0]}, '{user[1]}', '{user[2]}', {user[3]}, {user[4]}, {user[5]})
        """)
    print(f'  Inserted {len(users_data)} users')

    orders_data = [
        (1, 1, 'Widget', 2, 59.98),
        (2, 1, 'Gadget', 1, 29.99),
        (3, 2, 'Widget', 3, 89.97),
        (4, 2, 'Gizmo', 5, 49.95),
        (5, 3, 'Gadget', 2, 59.98),
        (6, 4, 'Widget', 1, 29.99),
        (7, 4, 'Gizmo', 3, 29.97),
        (8, 5, 'Gadget', 4, 119.96),
    ]

    print('\nInserting orders...')
    for order in orders_data:
        db.execute(f"""
            INSERT INTO orders (id, user_id, product, quantity, total)
            VALUES ({order[0]}, {order[1]}, '{order[2]}', {order[3]}, {order[4]})
        """)
    print(f'  Inserted {len(orders_data)} orders')

    # SELECT queries
    print_section('3. SELECT Queries')

    # Select all users
    results = db.query('SELECT * FROM users')
    print_results(results, 'All Users')

    # WHERE clause
    print_section('4. WHERE Clause')

    results = db.query('SELECT name, age, salary FROM users WHERE age > 30')
    print_results(results, 'Users older than 30')

    results = db.query('SELECT name, salary FROM users WHERE active = true ORDER BY salary DESC')
    print_results(results, 'Active users ordered by salary (descending)')

    # AND/OR
    print_section('5. AND/OR Conditions')

    results = db.query("""
        SELECT name, age, salary FROM users
        WHERE age >= 28 AND salary > 60000
    """)
    print_results(results, 'Users with age >= 28 AND salary > 60000')

    results = db.query("""
        SELECT name, age FROM users
        WHERE age < 26 OR age > 32
    """)
    print_results(results, 'Users younger than 26 OR older than 32')

    # LIKE
    print_section('6. LIKE Pattern Matching')

    results = db.query("SELECT name, email FROM users WHERE name LIKE '%son%'")
    print_results(results, "Users with 'son' in their name")

    results = db.query("SELECT name, email FROM users WHERE email LIKE '%@example.com'")
    print_results(results, 'Users with @example.com email')

    # IN clause
    print_section('7. IN Clause')

    results = db.query('SELECT name, age FROM users WHERE id IN (1, 3, 5)')
    print_results(results, 'Users with id 1, 3, or 5')

    # ORDER BY
    print_section('8. ORDER BY')

    results = db.query('SELECT name, age FROM users ORDER BY age ASC LIMIT 3')
    print_results(results, 'Three youngest users')

    # Aggregations
    print_section('9. Aggregations')

    results = db.query('SELECT COUNT(*) FROM users')
    print_results(results, 'Total user count')

    results = db.query('SELECT AVG(salary), MIN(salary), MAX(salary), SUM(salary) FROM users')
    print_results(results, 'Salary statistics')

    # GROUP BY
    print_section('10. GROUP BY')

    results = db.query("""
        SELECT product, COUNT(*), SUM(quantity), AVG(total)
        FROM orders
        GROUP BY product
    """)
    print_results(results, 'Order statistics by product')

    results = db.query("""
        SELECT active, COUNT(*), AVG(salary)
        FROM users
        GROUP BY active
    """)
    print_results(results, 'User statistics by active status')

    # JOINs
    print_section('11. JOIN Queries')

    results = db.query("""
        SELECT users.name, orders.product, orders.quantity, orders.total
        FROM users
        JOIN orders ON users.id = orders.user_id
        ORDER BY users.name, orders.total DESC
    """)
    print_results(results, 'Users with their orders')

    results = db.query("""
        SELECT users.name, SUM(orders.total)
        FROM users
        JOIN orders ON users.id = orders.user_id
        GROUP BY users.name
        ORDER BY SUM(orders.total) DESC
    """)
    print_results(results, 'Total order value by user')

    # UPDATE
    print_section('12. UPDATE')

    print('\nGiving Alice a 10% raise...')
    affected = db.execute('UPDATE users SET salary = 82500.0 WHERE id = 1')
    print(f'  Updated {affected} row(s)')

    results = db.query('SELECT name, salary FROM users WHERE id = 1')
    print_results(results, "Alice's updated salary")

    # DELETE
    print_section('13. DELETE')

    print('\nDeactivating users older than 33...')
    affected = db.execute('UPDATE users SET active = false WHERE age > 33')
    print(f'  Updated {affected} row(s)')

    results = db.query('SELECT name, age, active FROM users ORDER BY age DESC')
    print_results(results, 'Users with updated active status')

    # Persistence
    print_section('14. Persistence')

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name

    print(f'\nSaving database to {filepath}...')
    db.save(filepath)
    print('  Database saved successfully!')

    print('\nLoading database from file...')
    loaded_db = MiniDB.load(filepath)
    print('  Database loaded successfully!')

    results = loaded_db.query('SELECT COUNT(*) FROM users')
    print_results(results, 'User count in loaded database')

    os.unlink(filepath)
    print('\nCleaned up temporary file')

    # Summary
    print_section('Demo Complete!')
    print('\nMiniDB successfully demonstrated:')
    print('  ✓ CREATE TABLE with typed columns')
    print('  ✓ INSERT with various data types')
    print('  ✓ SELECT with column selection')
    print('  ✓ WHERE with comparisons (=, >, <, >=, <=)')
    print('  ✓ AND/OR boolean logic')
    print('  ✓ LIKE pattern matching')
    print('  ✓ IN clause')
    print('  ✓ ORDER BY ascending/descending')
    print('  ✓ LIMIT clause')
    print('  ✓ GROUP BY with aggregations')
    print('  ✓ COUNT, SUM, AVG, MIN, MAX')
    print('  ✓ INNER JOIN between tables')
    print('  ✓ UPDATE operations')
    print('  ✓ DELETE operations')
    print('  ✓ Persistence to/from JSON')
    print()


if __name__ == '__main__':
    main()
