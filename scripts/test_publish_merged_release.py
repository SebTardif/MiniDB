#!/usr/bin/env python3
"""A merged chore(release) commit is what gets tagged."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'publish-merged-release.sh'
WORKFLOW = ROOT / '.github' / 'workflows' / 'release.yml'


def run_script(env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop('GH_TOKEN', None)
    merged.pop('GITHUB_TOKEN', None)
    merged.pop('GITHUB_ENV', None)
    merged.update(env)
    return subprocess.run(
        ['bash', str(SCRIPT)],
        capture_output=True,
        text=True,
        env=merged,
        cwd=cwd,
        check=False,
    )


class PublishMergedReleaseTests(unittest.TestCase):
    def test_rejects_missing_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script({'GH_REPO': 'SebTardif/MiniDB', 'DRY_RUN': '1'}, Path(tmp))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pyproject.toml', result.stderr)

    def test_dry_run_creates_the_version_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pyproject.toml').write_text(
                '[project]\nname = "minidb"\nversion = "1.2.3"\n',
                encoding='utf-8',
            )
            result = run_script(
                {'GH_REPO': 'SebTardif/MiniDB', 'DRY_RUN': '1', 'GITHUB_SHA': 'abc123'},
                root,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gh release create v1.2.3', result.stdout)
        self.assertIn('--target abc123', result.stdout)
        self.assertIn('--generate-notes', result.stdout)
        self.assertIn('OK: dry run', result.stdout)

    def test_dry_run_uses_the_changelog_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pyproject.toml').write_text(
                '[project]\nname = "minidb"\nversion = "1.2.3"\n',
                encoding='utf-8',
            )
            (root / 'CHANGELOG.md').write_text(
                '# CHANGELOG\n\n## v1.2.3 (2026-11-08)\n\n### Fix\n\n- SQL results\n\n## v1.2.0 (2026-09-01)\n\n### Fix\n\n- Older\n',
                encoding='utf-8',
            )
            result = run_script(
                {'GH_REPO': 'SebTardif/MiniDB', 'DRY_RUN': '1', 'GITHUB_SHA': 'abc123'},
                root,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--notes-file ', result.stdout)
        self.assertNotIn('--generate-notes', result.stdout)

    def test_publish_waits_for_the_merged_release_commit(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        publish = text.split('name: Publish GitHub Release', 1)[1]
        self.assertIn('bash scripts/publish-merged-release.sh', publish)
        self.assertIn("startsWith(github.event.head_commit.message || '', 'chore(release):')", publish)
        self.assertNotIn("steps.release.outputs.released == 'true'", publish)
        self.assertIn('bash scripts/apply-release-notes.sh', publish)


if __name__ == '__main__':
    unittest.main()
