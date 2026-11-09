# MiniDB

Stdlib-only in-memory SQL engine. Python 3.11+.

## Verify

```bash
ruff check .
ruff format --check .
mypy minidb_sql/
python -m pytest tests/ --cov=minidb_sql --cov-report=term-missing
```

## Commits

Use a Conventional Commits prefix. Sign every commit with `git commit -s`.
The sign-off email is `git config user.email`.

Product pulls are squash-merged after the required checks are green.
Dependabot minor and patch updates auto-merge. A release still needs an explicit yes.
