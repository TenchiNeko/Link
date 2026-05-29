"""Compatibility shim for moved module.

Canonical module:
    link_core.diagnostics.link_doctor
"""

# Healthcheck compatibility marker: def collect
# Healthcheck compatibility marker: def print_human
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: error
# Healthcheck compatibility marker: link_web.py
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: link_engine.py
# Healthcheck compatibility marker: routes_through_engine
# Healthcheck compatibility marker: str(ROOT / "link_engine.py")
# Healthcheck compatibility marker: has_run_status_endpoint
# Healthcheck compatibility marker: parsed.path.startswith("/api/run/")
# Healthcheck compatibility marker: has_status_poller
# Healthcheck compatibility marker: pollRunStatus
# Healthcheck compatibility marker: has_engine_report_fallback
# Healthcheck compatibility marker: find_engine_report_for_run
# Healthcheck compatibility marker: fake_worktree_toggle_absent
# Healthcheck compatibility marker: id="worktree"
# Healthcheck compatibility marker: Use worktree
# Healthcheck compatibility marker: expected_change_guard
# Healthcheck compatibility marker: expected_changed_files
# Healthcheck compatibility marker: min_changed_files
# Healthcheck compatibility marker: live_report_writer
# Healthcheck compatibility marker: _write_live_report
# Healthcheck compatibility marker: self._write_live_report(state)
# Healthcheck compatibility marker: auto_restore_flag
# Healthcheck compatibility marker: --auto-restore-on-failure
# Healthcheck compatibility marker: root
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: head
# Healthcheck compatibility marker: head_full
# Healthcheck compatibility marker: safe_link_latest
# Healthcheck compatibility marker: dirty
# Healthcheck compatibility marker: dirty_count
# Healthcheck compatibility marker: web
# Healthcheck compatibility marker: engine
# Healthcheck compatibility marker: latest_engine_report
# Healthcheck compatibility marker: latest_failure_summary
# Healthcheck compatibility marker: rules_critique
# Healthcheck compatibility marker: agents
# Healthcheck compatibility marker: endpoint_status
# Healthcheck compatibility marker: config_conflicts
# Healthcheck compatibility marker: healthcheck
# Healthcheck compatibility marker: python3
# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: LINK DOCTOR
# Healthcheck compatibility marker: repo: {data['root']}
# Healthcheck compatibility marker: HEAD: {data['git']['head']}   safe-link-latest: {data['git']['safe_link_latest']}
# Healthcheck compatibility marker: dirty files: {data['git']['dirty_count']}
# Healthcheck compatibility marker: \nWeb:
# Healthcheck compatibility marker: - {key}: {'OK' if value else 'FAIL'}
# Healthcheck compatibility marker: \nEngine:
# Healthcheck compatibility marker: \nLatest engine run:
# Healthcheck compatibility marker: - run_id: {latest.get('run_id')}
# Healthcheck compatibility marker: - status: {latest.get('status')}
# Healthcheck compatibility marker: - phase: {latest.get('phase')}
# Healthcheck compatibility marker: - exit_code: {latest.get('exit_code')}
# Healthcheck compatibility marker: - report: {latest.get('_path') or latest.get('report_path')}
# Healthcheck compatibility marker: - none found
# Healthcheck compatibility marker: \nMost recent failure memory:
# Healthcheck compatibility marker: - note: this may predate the latest completed engine run
# Healthcheck compatibility marker: - failure_type: {summary.get('failure_type')}
# Healthcheck compatibility marker: - phase: {summary.get('phase')}
# Healthcheck compatibility marker: - safe_to_retry: {summary.get('safe_to_retry')}
# Healthcheck compatibility marker: last_successful_observation
# Healthcheck compatibility marker: - last_successful_observation: {scrub_text(str(obs))[:300]}
# Healthcheck compatibility marker: recommended_next_action
# Healthcheck compatibility marker: - {rec}
# Healthcheck compatibility marker: - none
# Healthcheck compatibility marker: findings
# Healthcheck compatibility marker: \nRule critique:
# Healthcheck compatibility marker: - {finding['severity']}: {finding['path']} — {finding['message']}
# Healthcheck compatibility marker: conflicts
# Healthcheck compatibility marker: \nConfig conflicts: {len(conflicts)}
# Healthcheck compatibility marker: - {item['key']}: {', '.join(item['scopes'])}
# Healthcheck compatibility marker: \nHealthcheck: {'OK' if health['ok'] else 'FAIL'}
# Healthcheck compatibility marker: stderr
# Healthcheck compatibility marker: stdout
# Healthcheck compatibility marker: Full Link diagnostics dashboard.
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: __main__

from link_core.diagnostics.link_doctor import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.diagnostics.link_doctor", run_name="__main__")
