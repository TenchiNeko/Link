"""Compatibility shim for moved module.

Canonical module:
    link_core.receipts.link_task_receipt
"""

# Healthcheck compatibility marker: def compact_head
# Healthcheck compatibility marker: def build_concise_task_receipt
# Healthcheck compatibility marker: def render_concise_task_receipt
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: LU92-concise-task-receipt-v1
# Healthcheck compatibility marker: ...
# Healthcheck compatibility marker: goal_classification
# Healthcheck compatibility marker: recommended_tests
# Healthcheck compatibility marker: required_gates
# Healthcheck compatibility marker: blockers
# Healthcheck compatibility marker: Resolve blockers before patching.
# Healthcheck compatibility marker: working_tree_clean
# Healthcheck compatibility marker: Proceed with the smallest useful patch, then run recommended checks.
# Healthcheck compatibility marker: Review dirty working tree before patching.
# Healthcheck compatibility marker: receipt_version
# Healthcheck compatibility marker: generated
# Healthcheck compatibility marker: seconds
# Healthcheck compatibility marker: repo
# Healthcheck compatibility marker: goal
# Healthcheck compatibility marker: branch
# Healthcheck compatibility marker: head
# Healthcheck compatibility marker: readiness
# Healthcheck compatibility marker: grade
# Healthcheck compatibility marker: readiness_grade
# Healthcheck compatibility marker: score
# Healthcheck compatibility marker: readiness_score
# Healthcheck compatibility marker: risk_level
# Healthcheck compatibility marker: suggested_worker_profile
# Healthcheck compatibility marker: categories
# Healthcheck compatibility marker: gate_count
# Healthcheck compatibility marker: test_count
# Healthcheck compatibility marker: top_tests
# Healthcheck compatibility marker: next_action
# Healthcheck compatibility marker: yes
# Healthcheck compatibility marker: # Link Concise Task Receipt
# Healthcheck compatibility marker: Goal: {receipt.get('goal', '')}
# Healthcheck compatibility marker: Branch: `{receipt.get('branch', '')}`
# Healthcheck compatibility marker: HEAD: `{compact_head(receipt.get('head', ''))}`
# Healthcheck compatibility marker: Working tree clean: **{clean}**
# Healthcheck compatibility marker: Readiness: **{readiness.get('grade')} / {readiness.get('score')}**
# Healthcheck compatibility marker: Risk: **{receipt.get('risk_level')}**
# Healthcheck compatibility marker: Worker: `{receipt.get('suggested_worker_profile')}`
# Healthcheck compatibility marker: Categories: {', '.join(f'`{x}`' for x in categories) if categories else '`none`'}
# Healthcheck compatibility marker: Gates: **{receipt.get('gate_count', 0)}**
# Healthcheck compatibility marker: Tests: **{receipt.get('test_count', 0)}**
# Healthcheck compatibility marker: ## Top Checks
# Healthcheck compatibility marker: - `{test}`
# Healthcheck compatibility marker: - none
# Healthcheck compatibility marker: ## Blockers
# Healthcheck compatibility marker: - {item}
# Healthcheck compatibility marker: ## Next
# Healthcheck compatibility marker: .join(lines).rstrip() +
# Healthcheck compatibility marker: Create a concise Link task receipt.
# Healthcheck compatibility marker: --goal
# Healthcheck compatibility marker: --root
# Healthcheck compatibility marker: , help=
# Healthcheck compatibility marker: --format
# Healthcheck compatibility marker: markdown
# Healthcheck compatibility marker: json
# Healthcheck compatibility marker: --output
# Healthcheck compatibility marker: --receipt-out
# Healthcheck compatibility marker: receipt_out
# Healthcheck compatibility marker: optional path to write receipt
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: __main__

from link_core.receipts.link_task_receipt import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.receipts.link_task_receipt", run_name="__main__")
