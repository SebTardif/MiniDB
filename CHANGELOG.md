# CHANGELOG

All notable changes to this project will be documented in this file.

This changelog is updated by
[release-please](https://github.com/googleapis/release-please).

<!-- version list -->

## [1.4.0](https://github.com/SebTardif/MiniDB/compare/v1.3.1...v1.4.0) (2026-11-18)


### Features

* accept table aliases so a table can be joined to itself ([#63](https://github.com/SebTardif/MiniDB/issues/63)) ([c919d9d](https://github.com/SebTardif/MiniDB/commit/c919d9d3a9b4e41f94471c933819b85949869372))


### Bug Fixes

* accept bare INSERT values, LIMIT parameters, and empty input ([#61](https://github.com/SebTardif/MiniDB/issues/61)) ([ac4d980](https://github.com/SebTardif/MiniDB/commit/ac4d980de6807c737759163783b9050882808b01))
* accept DEFAULT in CREATE TABLE ([#58](https://github.com/SebTardif/MiniDB/issues/58)) ([6a39a2d](https://github.com/SebTardif/MiniDB/commit/6a39a2d83cdef820a0e576a91aff5d237c3b4702))
* allow ORDER BY of an aggregate expression ([#57](https://github.com/SebTardif/MiniDB/issues/57)) ([0b4c6d4](https://github.com/SebTardif/MiniDB/commit/0b4c6d4c8d9786c37133c241622d5f8cf0fffcbb))
* count distinct non-null values ([#60](https://github.com/SebTardif/MiniDB/issues/60)) ([da17d47](https://github.com/SebTardif/MiniDB/commit/da17d47c57b05902f15beb32e32cc42fa9ca7331))
* do not treat a boolean as an integer ([#54](https://github.com/SebTardif/MiniDB/issues/54)) ([3d02f99](https://github.com/SebTardif/MiniDB/commit/3d02f99c4bda0d4249702f41014d38ef02172c9d))
* keep a boolean column in an unaliased SELECT * ([#64](https://github.com/SebTardif/MiniDB/issues/64)) ([0d23c4b](https://github.com/SebTardif/MiniDB/commit/0d23c4b166c9c4c76672f9ecf30563afe9f0939e))
* print finite demo floats with math.isfinite ([#66](https://github.com/SebTardif/MiniDB/issues/66)) ([6c68ca2](https://github.com/SebTardif/MiniDB/commit/6c68ca21810340af53be57542e311549b25092ea))
* refuse save while a transaction is open ([#56](https://github.com/SebTardif/MiniDB/issues/56)) ([ec40f4e](https://github.com/SebTardif/MiniDB/commit/ec40f4e5a9ebceb7b035f9a732224f5e5a36aae7))
* reject non-SELECT in query() before it runs ([#62](https://github.com/SebTardif/MiniDB/issues/62)) ([8dc427b](https://github.com/SebTardif/MiniDB/commit/8dc427bd0ceabacc8ae4597c7112f06b6d0ac888))
* type-check the boolean that is actually compared ([#65](https://github.com/SebTardif/MiniDB/issues/65)) ([1e487f1](https://github.com/SebTardif/MiniDB/commit/1e487f1e24b388f655fb8b4065beca2891ed61ff))

## [1.3.1](https://github.com/SebTardif/MiniDB/compare/v1.3.0...v1.3.1) (2026-11-09)


### Bug Fixes

* keep sort, LIKE, and snapshots on MiniDB errors ([#49](https://github.com/SebTardif/MiniDB/issues/49)) ([1ff92f7](https://github.com/SebTardif/MiniDB/commit/1ff92f703e33cd55d65fa60f06429996687a41f9))

## [1.3.0](https://github.com/SebTardif/MiniDB/compare/v1.2.0...v1.3.0) (2026-11-09)


### Features

* add searched CASE in the select list ([#37](https://github.com/SebTardif/MiniDB/issues/37)) ([bff4592](https://github.com/SebTardif/MiniDB/commit/bff45920679cd1e649cd8f38357462e6ac6f71f1))
* publish the library as minidb-sql ([#43](https://github.com/SebTardif/MiniDB/issues/43)) ([5236297](https://github.com/SebTardif/MiniDB/commit/5236297bf203844ceb56980ab01454e34acc2937))


### Bug Fixes

* cast column defaults and reject duplicate names ([#36](https://github.com/SebTardif/MiniDB/issues/36)) ([8aa5792](https://github.com/SebTardif/MiniDB/commit/8aa5792ef020afda47c878cbb8f71a508e110949))
* make WHERE NULL, comments, and deep parentheses safe ([#35](https://github.com/SebTardif/MiniDB/issues/35)) ([18583a0](https://github.com/SebTardif/MiniDB/commit/18583a016be83ae9093b3604a03241dc383a5d3d))
* read qualified columns on joins and aggregates ([#31](https://github.com/SebTardif/MiniDB/issues/31)) ([cc031cb](https://github.com/SebTardif/MiniDB/commit/cc031cb6e405e90417216ec727eee26c19019c76))
* reject bad column clauses and index parenthesized AND ([#33](https://github.com/SebTardif/MiniDB/issues/33)) ([8483436](https://github.com/SebTardif/MiniDB/commit/8483436ad3cfa80185b4378f9710b002fa5777f9))
* resolve a primary-key range in one pass ([#25](https://github.com/SebTardif/MiniDB/issues/25)) ([aab11bd](https://github.com/SebTardif/MiniDB/commit/aab11bd3538e18d03babb15f7d89d5788bd78dc2))
* stop MiniDB from returning wrong SQL results ([#24](https://github.com/SebTardif/MiniDB/issues/24)) ([4d6edfb](https://github.com/SebTardif/MiniDB/commit/4d6edfbeac6f0d47c20a4b903643a837cd1be871))


### Documentation

* add the README status badges ([#39](https://github.com/SebTardif/MiniDB/issues/39)) ([5a3febc](https://github.com/SebTardif/MiniDB/commit/5a3febc341542c0036ba131d2142fa0e511e834a))
* list v1.1.0 and v1.2.0 in the changelog ([#32](https://github.com/SebTardif/MiniDB/issues/32)) ([349a396](https://github.com/SebTardif/MiniDB/commit/349a3960aa384db14b37a6d1b5b89ffc2eb78d84)), closes [#30](https://github.com/SebTardif/MiniDB/issues/30)
* point the CI badge at main ([#40](https://github.com/SebTardif/MiniDB/issues/40)) ([9985519](https://github.com/SebTardif/MiniDB/commit/99855197f50f9a84db6caee7fa64957e3de4692d))

## v1.2.0 (2026-09-09)

### Features

- HAVING, bound parameters, and snapshot transactions (#13)

## v1.1.0 (2026-09-09)

### Features

- DISTINCT, IS NULL, explain, and SQL correctness (#10)

### Continuous Integration

- Pin ruff 0.16.6 and format README fences (#12)

### Build System

- Bump the actions group (#9)
- Bump the python group (#8)

## v1.0.3 (2026-07-02)

### Fix

- Mixed ASC/DESC ORDER BY (#5)

### Tests

- Extra tests, double-sort fix, docs and CI (#4)

## v1.0.2 (2026-07-02)

### Fix

- Eliminate import cycle between database and persistence

## v1.0.1 (2026-07-02)

### Fix

- Python 3.14 license classifier
- Semantic-release build command installs build

## v1.0.0 (Initial Release)

### Features

- CREATE TABLE with typed columns (INTEGER, STRING, FLOAT, BOOLEAN)
- INSERT, SELECT, UPDATE, DELETE operations
- WHERE clause with AND/OR, comparisons, LIKE, IN
- ORDER BY (ASC/DESC) and LIMIT
- GROUP BY with aggregations (COUNT, SUM, AVG, MIN, MAX)
- INNER JOIN between tables
- Automatic hash-based indexing on primary keys
- Query planner with index scan vs table scan
- Persistence to JSON files with versioning
