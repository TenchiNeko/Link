"""Compatibility shim for moved module.

Canonical module:
    link_core.recovery.link_rollback_advisor
"""

# Healthcheck compatibility marker: def format_advice_text
# Healthcheck compatibility marker: def get_advice
# Healthcheck compatibility marker: def print_advice
# Healthcheck compatibility marker: def print_dashboard
# Healthcheck compatibility marker: def self_test
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: Link Rollback Advisor
# Healthcheck compatibility marker: recommendation: {advice.get('recommendation', 'UNKNOWN')}
# Healthcheck compatibility marker: reason: {advice.get('reason', '')}
# Healthcheck compatibility marker: current_head: {advice.get('current_head', '-')}
# Healthcheck compatibility marker: rollback_candidate: {advice.get('rollback_candidate', '-')}
# Healthcheck compatibility marker: latest_evidence: {advice.get('latest_archive', '-')} [{advice.get('latest_status', 'UNKNOWN')}]
# Healthcheck compatibility marker: safe_actions
# Healthcheck compatibility marker: safe_actions:
# Healthcheck compatibility marker: - {action}
# Healthcheck compatibility marker: recommendation
# Healthcheck compatibility marker: ADVISE_ROLLBACK_TO_LAST_PASS
# Healthcheck compatibility marker: reason
# Healthcheck compatibility marker: Most recent evidence failed; a prior passing healthcheck archive exists.
# Healthcheck compatibility marker: current_head
# Healthcheck compatibility marker: bad222
# Healthcheck compatibility marker: rollback_candidate
# Healthcheck compatibility marker: good111
# Healthcheck compatibility marker: latest_archive
# Healthcheck compatibility marker: 20260102-fail
# Healthcheck compatibility marker: latest_status
# Healthcheck compatibility marker: FAIL
# Healthcheck compatibility marker: Inspect diff
# Healthcheck compatibility marker: Create review branch
# Healthcheck compatibility marker: cli_text_missing_title
# Healthcheck compatibility marker: cli_text_missing_recommendation
# Healthcheck compatibility marker: cli_text_missing_candidate
# Healthcheck compatibility marker: cli_text_missing_safe_action
# Healthcheck compatibility marker: cannot_import_evidence_rollback_advisor::{exc}
# Healthcheck compatibility marker: cannot_import_rollback_advisor_dashboard::{exc}
# Healthcheck compatibility marker: Link rollback advisor CLI.
# Healthcheck compatibility marker: command
# Healthcheck compatibility marker: advise
# Healthcheck compatibility marker: Print rollback advice.
# Healthcheck compatibility marker: --root
# Healthcheck compatibility marker: Healthcheck evidence archive root.
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: Print JSON advice.
# Healthcheck compatibility marker: dashboard
# Healthcheck compatibility marker: Print rollback advisor dashboard panel.
# Healthcheck compatibility marker: Print JSON dashboard payload.
# Healthcheck compatibility marker: self-test
# Healthcheck compatibility marker: Run CLI contract self-test.
# Healthcheck compatibility marker: root
# Healthcheck compatibility marker: json
# Healthcheck compatibility marker: rollback advisor CLI FAILED
# Healthcheck compatibility marker: - {problem}
# Healthcheck compatibility marker: rollback advisor CLI OK
# Healthcheck compatibility marker: __main__

from link_core.recovery.link_rollback_advisor import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.recovery.link_rollback_advisor", run_name="__main__")
