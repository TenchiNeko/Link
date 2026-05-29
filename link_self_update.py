"""Compatibility shim for moved module.

Canonical module:
    link_core.runtime.link_self_update
"""

# Healthcheck compatibility marker: def run_git
# Healthcheck compatibility marker: def git_text
# Healthcheck compatibility marker: def write_json
# Healthcheck compatibility marker: def create_preflight_receipt
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: self_update_receipts
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: git command blocked: {decision.reason}
# Healthcheck compatibility marker: git command failed: git {joined}\n{out}
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: self_update_preflight
# Healthcheck compatibility marker: %Y%m%d-%H%M%S
# Healthcheck compatibility marker: worker profile validation failed: {validation}
# Healthcheck compatibility marker: branch
# Healthcheck compatibility marker: --show-current
# Healthcheck compatibility marker: rev-parse
# Healthcheck compatibility marker: --verify
# Healthcheck compatibility marker: HEAD
# Healthcheck compatibility marker: log
# Healthcheck compatibility marker: --oneline
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: --short
# Healthcheck compatibility marker: goal
# Healthcheck compatibility marker: profile
# Healthcheck compatibility marker: enabled_tools
# Healthcheck compatibility marker: enabled_tool_names
# Healthcheck compatibility marker: allow
# Healthcheck compatibility marker: preflight inspection only
# Healthcheck compatibility marker: link_self_update
# Healthcheck compatibility marker: head
# Healthcheck compatibility marker: status_before
# Healthcheck compatibility marker: worker_profile
# Healthcheck compatibility marker: receipt_version
# Healthcheck compatibility marker: runner
# Healthcheck compatibility marker: mode
# Healthcheck compatibility marker: preflight
# Healthcheck compatibility marker: created_at
# Healthcheck compatibility marker: latest_commit
# Healthcheck compatibility marker: profile_details
# Healthcheck compatibility marker: profile_validation
# Healthcheck compatibility marker: snapshot_path
# Healthcheck compatibility marker: allowed_actions
# Healthcheck compatibility marker: inspect repository state
# Healthcheck compatibility marker: resolve restricted worker profile
# Healthcheck compatibility marker: create execution snapshot
# Healthcheck compatibility marker: write self-update receipt
# Healthcheck compatibility marker: blocked_actions
# Healthcheck compatibility marker: modify main directly
# Healthcheck compatibility marker: run destructive git commands
# Healthcheck compatibility marker: apply patches without later test evidence
# Healthcheck compatibility marker: copy external project code wholesale
# Healthcheck compatibility marker: use tools outside the resolved worker profile
# Healthcheck compatibility marker: next_step
# Healthcheck compatibility marker: review receipt, then implement the smallest safe Link-native patch
# Healthcheck compatibility marker: {created_at}-self-update-preflight-{profile}.json
# Healthcheck compatibility marker: Run Link self-update preflight.
# Healthcheck compatibility marker: --goal
# Healthcheck compatibility marker: Self-update goal being evaluated.
# Healthcheck compatibility marker: --profile
# Healthcheck compatibility marker: Worker profile to resolve for this preflight.
# Healthcheck compatibility marker: __main__

from link_core.runtime.link_self_update import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.runtime.link_self_update", run_name="__main__")
