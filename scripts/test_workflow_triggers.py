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

    def test_dependabot_auto_merge_stays_off_pr_code(self) -> None:
        text = (WORKFLOWS / 'dependabot-auto-merge.yml').read_text(encoding='utf-8')
        on_block = _on_block(text)
        self.assertIn('pull_request_target:', on_block)
        self.assertIn('workflow_dispatch:', on_block)
        self.assertNotIn('actions/checkout', text)
        self.assertIn('gh pr merge --auto --squash', text)
        self.assertIn('version-update:semver-major', text)
        self.assertIn('timeout-minutes: 5', text)

    def test_dco_and_security_cover_merge_group(self) -> None:
        dco = (WORKFLOWS / 'dco.yml').read_text(encoding='utf-8')
        security = (WORKFLOWS / 'security.yml').read_text(encoding='utf-8')
        self.assertIn('merge_group:', _on_block(dco))
        self.assertIn('name: DCO Sign-off', dco)
        self.assertIn('bash scripts/check-dco.sh', dco)
        self.assertIn('merge_group:', _on_block(security))
        self.assertIn('CodeQL (${{ matrix.language }})', security)

    def test_ci_gate_requires_workflow_sanity(self) -> None:
        text = (WORKFLOWS / 'ci.yml').read_text(encoding='utf-8')
        self.assertIn('name: ci', text)
        self.assertIn('name: Workflow sanity', text)
        self.assertIn('needs: [lint, type-check, test, workflow-sanity]', text)

    def test_auto_approve_does_not_merge(self) -> None:
        text = (WORKFLOWS / 'auto-approve.yml').read_text(encoding='utf-8')
        self.assertNotIn('gh pr merge', text)
        self.assertIn("github.actor == 'SebTardif'", text)

    def test_actions_are_pinned(self) -> None:
        roots = [WORKFLOWS, ROOT / '.github' / 'actions']
        for root in roots:
            for path in root.rglob('*.yml'):
                for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
                    if 'uses:' not in line or '@' not in line:
                        continue
                    self.assertRegex(
                        line,
                        r'@[0-9a-f]{40}\b',
                        f'{path}:{line_number} is not pinned to a commit',
                    )


if __name__ == '__main__':
    unittest.main()
