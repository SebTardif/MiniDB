#!/usr/bin/env python3
"""Lock Recipe A (no push-to-main compile) and notes-branch apply."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'


def _on_block(text: str) -> str:
    start = text.index('\non:')
    rest = text[start + 1 :]
    end = rest.index('\njobs:')
    block = rest[:end]
    lines = []
    for line in block.splitlines():
        stripped = line.split('#', 1)[0].rstrip()
        if stripped:
            lines.append(stripped)
    return '\n'.join(lines)


class WorkflowTriggerTests(unittest.TestCase):
    def test_ci_has_no_push_compile(self) -> None:
        on_block = _on_block((WORKFLOWS / 'ci.yml').read_text(encoding='utf-8'))
        self.assertIn('pull_request:', on_block)
        self.assertIn('workflow_dispatch:', on_block)
        self.assertNotIn('push:', on_block)
        self.assertNotIn('workflow_call:', on_block)

    def test_release_does_not_rerun_ci_matrix(self) -> None:
        text = (WORKFLOWS / 'release.yml').read_text(encoding='utf-8')
        self.assertNotIn('uses: ./.github/workflows/ci.yml', text)
        self.assertIn('bash scripts/apply-release-notes.sh', text)

    def test_apply_release_notes_is_dispatch_only(self) -> None:
        text = (WORKFLOWS / 'apply-release-notes.yml').read_text(encoding='utf-8')
        on_block = _on_block(text)
        self.assertIn('workflow_dispatch:', on_block)
        self.assertNotIn('pull_request:', on_block)
        self.assertNotIn('push:', on_block)


if __name__ == '__main__':
    unittest.main()
