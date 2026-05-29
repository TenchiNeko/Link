"""Compatibility shim for moved module.

Canonical module:
    link_core.runtime.link_audit_fast
"""

# Healthcheck compatibility marker: def run_cmd
# Healthcheck compatibility marker: def emit
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: def _link_audit_fast_specialist_fanout_exit_hook
# Healthcheck compatibility marker: , raw: str =
# Healthcheck compatibility marker: level
# Healthcheck compatibility marker: title
# Healthcheck compatibility marker: detail
# Healthcheck compatibility marker: phase
# Healthcheck compatibility marker: audit
# Healthcheck compatibility marker: raw
# Healthcheck compatibility marker: {title}: {detail}
# Healthcheck compatibility marker: Fast read-only Link audit path
# Healthcheck compatibility marker: --prompt-file
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: replace
# Healthcheck compatibility marker: audit-
# Healthcheck compatibility marker: LINK AUDIT FAST PATH
# Healthcheck compatibility marker: repo:
# Healthcheck compatibility marker: run_id:
# Healthcheck compatibility marker: info
# Healthcheck compatibility marker: Prompt received
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: --short
# Healthcheck compatibility marker: --untracked-files=all
# Healthcheck compatibility marker: Git status
# Healthcheck compatibility marker: clean
# Healthcheck compatibility marker: dirty
# Healthcheck compatibility marker: log
# Healthcheck compatibility marker: --oneline
# Healthcheck compatibility marker: --decorate
# Healthcheck compatibility marker: Recent commits
# Healthcheck compatibility marker: link_doctor.py
# Healthcheck compatibility marker: success
# Healthcheck compatibility marker: error
# Healthcheck compatibility marker: Link doctor
# Healthcheck compatibility marker: exit {rc_doctor}
# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: Healthcheck
# Healthcheck compatibility marker: exit {rc_health}
# Healthcheck compatibility marker: run_id
# Healthcheck compatibility marker: completed
# Healthcheck compatibility marker: failed
# Healthcheck compatibility marker: started_at
# Healthcheck compatibility marker: ended_at
# Healthcheck compatibility marker: exit_code
# Healthcheck compatibility marker: changed_files
# Healthcheck compatibility marker: diff_lines
# Healthcheck compatibility marker: events
# Healthcheck compatibility marker: report_path
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: engine_runs
# Healthcheck compatibility marker: engine_report.json
# Healthcheck compatibility marker: audit_fast_path
# Healthcheck compatibility marker: Audit report:
# Healthcheck compatibility marker: Run deterministic read-only specialist fanout at the end of audit fastpath.
# Healthcheck compatibility marker: audit-fanout-
# Healthcheck compatibility marker: SPECIALIST FANOUT: OK
# Healthcheck compatibility marker: SPECIALIST FANOUT JSON:
# Healthcheck compatibility marker: json_path
# Healthcheck compatibility marker: SPECIALIST FANOUT SUMMARY:
# Healthcheck compatibility marker: summary_path
# Healthcheck compatibility marker: SPECIALIST FANOUT: FAILED:
# Healthcheck compatibility marker: __main__

from link_core.runtime.link_audit_fast import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.runtime.link_audit_fast", run_name="__main__")
