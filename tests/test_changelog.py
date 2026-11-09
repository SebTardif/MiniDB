"""CHANGELOG.md must list released versions and accept the next one."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / 'CHANGELOG.md'
PYPROJECT = ROOT / 'pyproject.toml'
INSERTION_FLAG = '<!-- version list -->'


def test_changelog_lists_versions_through_the_current_tag() -> None:
    """Released tags after v1.0.3 are sections in the changelog."""
    text = CHANGELOG.read_text(encoding='utf-8')
    assert INSERTION_FLAG in text
    assert '<!--next-version-placeholder-->' not in text
    assert '## v1.2.0 (2026-09-09)' in text
    assert '## v1.1.0 (2026-09-09)' in text
    assert '## v1.0.3 (2026-07-02)' in text
    assert 'HAVING, bound parameters, and snapshot transactions (#13)' in text
    assert 'DISTINCT, IS NULL, explain, and SQL correctness (#10)' in text


def test_changelog_insertion_flag_matches_semantic_release() -> None:
    """Update mode writes a section only when this flag is in the file."""
    config = tomllib.loads(PYPROJECT.read_text(encoding='utf-8'))
    changelog = config['tool']['semantic_release']['changelog']
    assert changelog['mode'] == 'update'
    assert changelog['insertion_flag'] == INSERTION_FLAG
    assert INSERTION_FLAG in CHANGELOG.read_text(encoding='utf-8')
