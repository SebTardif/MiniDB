#!/usr/bin/env python3
"""One release-please pull tracks main. Old per-version branches are gone."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'release.yml'
CONFIG = ROOT / 'release-please-config.json'
MANIFEST = ROOT / '.release-please-manifest.json'


class ReleasePleaseTests(unittest.TestCase):
    def test_config_keeps_plain_v_tags_and_the_package_version(self) -> None:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        package = config['packages']['.']
        self.assertEqual(package['release-type'], 'python')
        self.assertEqual(package['changelog-path'], 'CHANGELOG.md')
        self.assertIs(package['include-component-in-tag'], False)
        paths = [item['path'] for item in package['extra-files']]
        self.assertIn('minidb_sql/__init__.py', paths)
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.assertEqual(manifest['.'], '1.2.0')

    def test_workflow_uses_one_release_please_pull(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7 # v5.0.0', text)
        self.assertIn('config-file: release-please-config.json', text)
        self.assertIn('manifest-file: .release-please-manifest.json', text)
        self.assertIn("needs.release-please.outputs.release_created == 'true'", text)
        self.assertIn('bash scripts/apply-release-notes.sh', text)
        self.assertNotIn('python-semantic-release', text)
        self.assertNotIn('open-release-pr.sh', text)
        self.assertNotIn('publish-merged-release.sh', text)
        self.assertNotIn('uses: ./.github/workflows/ci.yml', text)
        self.assertFalse((ROOT / 'scripts' / 'open-release-pr.sh').exists())
        self.assertFalse((ROOT / 'scripts' / 'publish-merged-release.sh').exists())


if __name__ == '__main__':
    unittest.main()
