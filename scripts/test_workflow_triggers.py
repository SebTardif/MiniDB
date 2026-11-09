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

    def test_workflows_filter_covers_scripts_and_actionlint(self) -> None:
        text = (WORKFLOWS / 'ci.yml').read_text(encoding='utf-8')
        marker = '\n            workflows:\n'
        block = text.split(marker, 1)[1].split('\n  lint:', 1)[0]
        self.assertIn("- 'scripts/**'", block)
        self.assertIn("- '.github/actionlint.yaml'", block)
        self.assertIn("- '.github/workflows/**'", block)
        self.assertIn("- '.github/actions/**'", block)
        self.assertIn("- '.github/zizmor.yml'", block)
        self.assertNotIn("- 'scripts/test_check_dco.py'", block)

    def test_ci_gate_requires_workflow_sanity(self) -> None:
        text = (WORKFLOWS / 'ci.yml').read_text(encoding='utf-8')
        on_block = _on_block(text)
        self.assertIn('name: ci', text)
        self.assertIn('name: Workflow sanity', text)
        self.assertIn('needs: [changes, lint, type-check, test, workflow-sanity]', text)
        self.assertIn('schedule:', on_block)
        self.assertIn('ready_for_review', text)
        self.assertIn('dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d', text)
        self.assertNotIn('if [ "$result" != "success" ]', text)

    def test_links_pull_request_has_no_path_filter(self) -> None:
        text = (WORKFLOWS / 'links.yml').read_text(encoding='utf-8')
        pull_request = text.split('pull_request:', 1)[1].split('schedule:', 1)[0]
        self.assertNotIn('paths:', pull_request)
        self.assertIn('name: Check Links', text)
        self.assertIn('lychee.toml', text)

    def test_security_keeps_required_codeql_names(self) -> None:
        text = (WORKFLOWS / 'security.yml').read_text(encoding='utf-8')
        self.assertIn('name: Gitleaks', text)
        self.assertIn('name: Trivy', text)
        self.assertIn('name: "CodeQL (${{ matrix.language }})"', text)
        self.assertIn('name: Dependency Review', text)
        self.assertNotIn('autobuild', text)

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
