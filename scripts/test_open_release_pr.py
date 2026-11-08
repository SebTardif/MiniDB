#!/usr/bin/env python3
"""The release branch is a pull request. main is never the push target."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'open-release-pr.sh'
WORKFLOW = ROOT / '.github' / 'workflows' / 'release.yml'


def run_script(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop('GH_TOKEN', None)
    merged.pop('GITHUB_TOKEN', None)
    merged.update(env)
    return subprocess.run(
        ['bash', str(SCRIPT)],
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


class OpenReleasePrTests(unittest.TestCase):
    def test_rejects_bad_version(self) -> None:
        result = run_script({'VERSION': 'v1.2.3', 'GH_REPO': 'SebTardif/MiniDB', 'DRY_RUN': '1'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('X.Y.Z', result.stderr)

    def test_dry_run_pushes_a_release_branch(self) -> None:
        result = run_script({'VERSION': '1.2.3', 'GH_REPO': 'SebTardif/MiniDB', 'DRY_RUN': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('HEAD:refs/heads/chore/release-1.2.3', result.stdout)
        self.assertIn('chore(release): v1.2.3', result.stdout)
        self.assertNotIn('refs/heads/main', result.stdout)
        self.assertIn('OK: dry run', result.stdout)

    def test_workflow_does_not_push_main(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        script = SCRIPT.read_text(encoding='utf-8')
        release_step = text.split('name: Python Semantic Release', 1)[1].split('name: Open release pull request', 1)[0]
        self.assertIn('--no-push', release_step)
        self.assertIn('--no-tag', release_step)
        self.assertIn('--no-vcs-release', release_step)
        self.assertIn('--skip-build', release_step)
        self.assertIn('bash scripts/open-release-pr.sh', text)
        self.assertNotIn('HEAD:refs/heads/main', script)
        self.assertNotIn('git push origin main', script)
        self.assertNotIn('git push origin HEAD:main', text)


if __name__ == '__main__':
    unittest.main()
