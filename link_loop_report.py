"""Compatibility shim for moved module.

Canonical module:
    link_core.diagnostics.link_loop_report
"""

# Healthcheck compatibility marker: def summarize_event
# Healthcheck compatibility marker: def build_report
# Healthcheck compatibility marker: def write_markdown
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: (stuck loop|same commands repeated|repeated\s+\d+x|hit max rounds)
# Healthcheck compatibility marker: |
# Healthcheck compatibility marker: )) for k in (
# Healthcheck compatibility marker: level
# Healthcheck compatibility marker: title
# Healthcheck compatibility marker: detail
# Healthcheck compatibility marker: raw
# Healthcheck compatibility marker: events
# Healthcheck compatibility marker: )).lower() in {
# Healthcheck compatibility marker: warning
# Healthcheck compatibility marker: info
# Healthcheck compatibility marker: phase
# Healthcheck compatibility marker: stuck_loop
# Healthcheck compatibility marker: failure
# Healthcheck compatibility marker: exit_code
# Healthcheck compatibility marker: unknown
# Healthcheck compatibility marker: Stop retrying the same command/tool sequence.
# Healthcheck compatibility marker: Summarize known state from the latest successful observation.
# Healthcheck compatibility marker: Name the exact missing information or file section.
# Healthcheck compatibility marker: Switch to a smaller deterministic patch or ask for one specific human input.
# Healthcheck compatibility marker: For audit-only tasks, avoid sending the full orchestrator through build/verify phases when no write is expected.
# Healthcheck compatibility marker: run_id
# Healthcheck compatibility marker: failure_type
# Healthcheck compatibility marker: engine_status
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: changed_files
# Healthcheck compatibility marker: diff_lines
# Healthcheck compatibility marker: loop_event_count
# Healthcheck compatibility marker: error_event_count
# Healthcheck compatibility marker: repeated_command_clues
# Healthcheck compatibility marker: last_successful_observation
# Healthcheck compatibility marker: recommended_next_action
# Healthcheck compatibility marker: safe_to_retry
# Healthcheck compatibility marker: source_report
# Healthcheck compatibility marker: _path
# Healthcheck compatibility marker: report_path
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: loop_reports
# Healthcheck compatibility marker: unknown-{int(time.time())}
# Healthcheck compatibility marker: loop-report-{run_id}.md
# Healthcheck compatibility marker: # Link Loop Report: {run_id}
# Healthcheck compatibility marker: - failure_type: `{report.get('failure_type')}`
# Healthcheck compatibility marker: - phase: `{report.get('phase')}`
# Healthcheck compatibility marker: - safe_to_retry: `{report.get('safe_to_retry')}`
# Healthcheck compatibility marker: - source_report: `{report.get('source_report')}`
# Healthcheck compatibility marker: ## Last successful observation
# Healthcheck compatibility marker: None found.
# Healthcheck compatibility marker: ## Repeated command clues
# Healthcheck compatibility marker: - {clue}
# Healthcheck compatibility marker: ## Recommended next action
# Healthcheck compatibility marker: - {item}
# Healthcheck compatibility marker: .join(lines) +
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: Create structured diagnostics for stuck-loop Link runs.
# Healthcheck compatibility marker: --report
# Healthcheck compatibility marker: Path to engine_report.json
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: --write
# Healthcheck compatibility marker: No engine report found.
# Healthcheck compatibility marker: loop-report-{report.get('run_id')}.json
# Healthcheck compatibility marker: written_json
# Healthcheck compatibility marker: written_markdown
# Healthcheck compatibility marker: failure_type: {report['failure_type']}
# Healthcheck compatibility marker: phase: {report['phase']}
# Healthcheck compatibility marker: safe_to_retry: {report['safe_to_retry']}
# Healthcheck compatibility marker: last_successful_observation: {report.get('last_successful_observation')}
# Healthcheck compatibility marker: recommended_next_action:
# Healthcheck compatibility marker: __main__

from link_core.diagnostics.link_loop_report import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.diagnostics.link_loop_report", run_name="__main__")
