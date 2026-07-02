# Contributing to MiniDB

## Prerequisites

- Python 3.11 or later
- No external dependencies for the library itself

## Development Setup

```bash
git clone https://github.com/SebTardif/MiniDB.git
cd MiniDB

# Install dev tools
pip install ruff mypy pytest pytest-cov

# Verify everything works
python -m pytest tests/ -v
python main.py
```

## Pre-Commit Checks

Run these before submitting a PR (CI enforces all of them):

```bash
# Lint
ruff check .

# Format
ruff format --check .

# Type check
mypy minidb/

# Tests
python -m pytest tests/ -v
```

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
for automatic versioning via semantic-release.

Allowed prefixes: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`,
`test`, `build`, `ci`, `chore`, `revert`.

Examples:
- `feat: add DISTINCT keyword support`
- `fix: handle NULL in ORDER BY correctly`
- `test: add edge case tests for JOIN`
- `docs: update SQL syntax reference`

## Project Structure

```
minidb/
  database.py      # MiniDB main class (facade)
  parser.py        # SQL lexer and parser
  query.py         # Query execution engine
  table.py         # Table storage and row management
  column.py        # Column and Schema definitions
  index.py         # Hash-based indexing
  planner.py       # Query planner (index vs table scan)
  persistence.py   # JSON serialization
  types.py         # Type definitions and enums
  errors.py        # Custom exception hierarchy
tests/
  test_*.py        # Test files matching source modules
```
