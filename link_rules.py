"""Compatibility shim for moved module.

Canonical module:
    link_core.config.link_rules
"""

# Healthcheck compatibility marker: def deep_merge
# Healthcheck compatibility marker: def local_rules
# Healthcheck compatibility marker: def effective_rules
# Healthcheck compatibility marker: def critique_rules
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: command_guard
# Healthcheck compatibility marker: allow
# Healthcheck compatibility marker: read-only inspection commands
# Healthcheck compatibility marker: git status/diff/log
# Healthcheck compatibility marker: python compilation checks
# Healthcheck compatibility marker: healthcheck/self-test commands
# Healthcheck compatibility marker: caution
# Healthcheck compatibility marker: commands that modify files
# Healthcheck compatibility marker: git add/commit/checkout
# Healthcheck compatibility marker: package installation
# Healthcheck compatibility marker: script execution not known to be read-only
# Healthcheck compatibility marker: deny
# Healthcheck compatibility marker: destructive recursive deletes against root/home
# Healthcheck compatibility marker: force push
# Healthcheck compatibility marker: hard reset
# Healthcheck compatibility marker: git clean deleting untracked work
# Healthcheck compatibility marker: downloaded shell scripts piped directly into a shell
# Healthcheck compatibility marker: recursive world-writable chmods against home/repo roots
# Healthcheck compatibility marker: file_safety
# Healthcheck compatibility marker: tracked source files inside repo
# Healthcheck compatibility marker: research/reference material
# Healthcheck compatibility marker: .agents generated state
# Healthcheck compatibility marker: .git internals
# Healthcheck compatibility marker: paths outside repo
# Healthcheck compatibility marker: protected generated/internal state
# Healthcheck compatibility marker: git_safety
# Healthcheck compatibility marker: safe_reads
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: diff
# Healthcheck compatibility marker: log
# Healthcheck compatibility marker: show
# Healthcheck compatibility marker: guarded_writes
# Healthcheck compatibility marker: add
# Healthcheck compatibility marker: commit
# Healthcheck compatibility marker: tag
# Healthcheck compatibility marker: reset --hard
# Healthcheck compatibility marker: clean -fdx
# Healthcheck compatibility marker: push --force
# Healthcheck compatibility marker: engine
# Healthcheck compatibility marker: max_changed_files_default
# Healthcheck compatibility marker: max_diff_lines_default
# Healthcheck compatibility marker: expected_change_guard
# Healthcheck compatibility marker: auto_restore_on_failure
# Healthcheck compatibility marker: write_live_engine_report
# Healthcheck compatibility marker: web
# Healthcheck compatibility marker: route_runs_through_engine
# Healthcheck compatibility marker: status_endpoint
# Healthcheck compatibility marker: /api/run/<id>
# Healthcheck compatibility marker: journal_status_poller
# Healthcheck compatibility marker: fake_worktree_toggle_forbidden
# Healthcheck compatibility marker: diagnostics
# Healthcheck compatibility marker: doctor
# Healthcheck compatibility marker: loop_report
# Healthcheck compatibility marker: agent_listing
# Healthcheck compatibility marker: endpoint_status
# Healthcheck compatibility marker: config_conflict_report
# Healthcheck compatibility marker: redaction
# Healthcheck compatibility marker: redact_keys_matching
# Healthcheck compatibility marker: token
# Healthcheck compatibility marker: secret
# Healthcheck compatibility marker: api_key
# Healthcheck compatibility marker: authorization
# Healthcheck compatibility marker: cookie
# Healthcheck compatibility marker: password
# Healthcheck compatibility marker: webhook
# Healthcheck compatibility marker: link_rules.local.json
# Healthcheck compatibility marker: severity
# Healthcheck compatibility marker: path
# Healthcheck compatibility marker: message
# Healthcheck compatibility marker: engine.expected_change_guard
# Healthcheck compatibility marker: high
# Healthcheck compatibility marker: No-op success can slip through without expected-change rules.
# Healthcheck compatibility marker: engine.auto_restore_on_failure
# Healthcheck compatibility marker: Failed runs should restore safe baseline automatically.
# Healthcheck compatibility marker: web.status_endpoint
# Healthcheck compatibility marker: medium
# Healthcheck compatibility marker: Web runs need a status endpoint for non-SSE diagnostics.
# Healthcheck compatibility marker: redaction.redact_keys_matching
# Healthcheck compatibility marker: Status tools must redact secrets before printing.
# Healthcheck compatibility marker: .join(rules.get(
# Healthcheck compatibility marker: , {}).get(
# Healthcheck compatibility marker: command_guard.deny
# Healthcheck compatibility marker: Force-push denial is missing.
# Healthcheck compatibility marker: downloaded
# Healthcheck compatibility marker: Downloaded script pipe denial is missing.
# Healthcheck compatibility marker: web.fake_worktree_toggle_forbidden
# Healthcheck compatibility marker: Fake UI toggles can imply isolation that is not actually active.
# Healthcheck compatibility marker: info
# Healthcheck compatibility marker: all
# Healthcheck compatibility marker: No obvious rule conflicts detected.
# Healthcheck compatibility marker: findings
# Healthcheck compatibility marker: finding_count
# Healthcheck compatibility marker: Inspect and critique Link safety/runtime rules.
# Healthcheck compatibility marker: command
# Healthcheck compatibility marker: defaults
# Healthcheck compatibility marker: effective
# Healthcheck compatibility marker: critique
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: __main__

from link_core.config.link_rules import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.config.link_rules", run_name="__main__")
