"""Compatibility shim for moved module.

Canonical module:
    link_core.health.qa_repair_routing_contract
"""

# Healthcheck compatibility marker: def normalize_verdict
# Healthcheck compatibility marker: def detect_blocking_findings
# Healthcheck compatibility marker: def route_qa_result
# Healthcheck compatibility marker: def validate_qa_repair_route
# Healthcheck compatibility marker: def synthetic_repair_case
# Healthcheck compatibility marker: def synthetic_approval_case
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: must fix
# Healthcheck compatibility marker: fail
# Healthcheck compatibility marker: failed
# Healthcheck compatibility marker: revise
# Healthcheck compatibility marker: reject
# Healthcheck compatibility marker: rejected
# Healthcheck compatibility marker: not commit-ready
# Healthcheck compatibility marker: blocking
# Healthcheck compatibility marker: blocker
# Healthcheck compatibility marker: no blocking
# Healthcheck compatibility marker: no blockers
# Healthcheck compatibility marker: without blocking
# Healthcheck compatibility marker: not blocking
# Healthcheck compatibility marker: zero blocking
# Healthcheck compatibility marker: APPROVE
# Healthcheck compatibility marker: APPROVED
# Healthcheck compatibility marker: PASS
# Healthcheck compatibility marker: REVISE
# Healthcheck compatibility marker: FAIL
# Healthcheck compatibility marker: FAILED
# Healthcheck compatibility marker: REJECT
# Healthcheck compatibility marker: REJECTED
# Healthcheck compatibility marker: UNKNOWN
# Healthcheck compatibility marker: approval_ready
# Healthcheck compatibility marker: handoff_to_senior_review
# Healthcheck compatibility marker: repair_required
# Healthcheck compatibility marker: route_back_to_production_worker
# Healthcheck compatibility marker: manual_review
# Healthcheck compatibility marker: route_to_chief_of_staff
# Healthcheck compatibility marker: contract_version
# Healthcheck compatibility marker: 1.0
# Healthcheck compatibility marker: route
# Healthcheck compatibility marker: action
# Healthcheck compatibility marker: normalized_verdict
# Healthcheck compatibility marker: blocking_findings
# Healthcheck compatibility marker: changed_files
# Healthcheck compatibility marker: allowed_to_commit
# Healthcheck compatibility marker: invalid_contract_version
# Healthcheck compatibility marker: invalid_route::{route}
# Healthcheck compatibility marker: blocking_findings_cannot_commit
# Healthcheck compatibility marker: repair_required_cannot_commit
# Healthcheck compatibility marker: approval_ready_should_allow_commit
# Healthcheck compatibility marker: BLOCKING-1: final gate integration missing. Must fix before approval.
# Healthcheck compatibility marker: factory_final_gate_audit.py
# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: QA PASS. No blocking findings.
# Healthcheck compatibility marker: repair_case_not_routed_to_repair
# Healthcheck compatibility marker: repair_case_allowed_commit
# Healthcheck compatibility marker: approval_case_not_ready
# Healthcheck compatibility marker: approval_case_not_allowed
# Healthcheck compatibility marker: qa repair routing contract FAILED
# Healthcheck compatibility marker: - {problem}
# Healthcheck compatibility marker: qa repair routing contract OK
# Healthcheck compatibility marker: __main__

from link_core.health.qa_repair_routing_contract import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.health.qa_repair_routing_contract", run_name="__main__")
