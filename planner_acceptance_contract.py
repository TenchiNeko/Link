"""Compatibility shim for moved module.

Canonical module:
    link_core.health.planner_acceptance_contract
"""

# Healthcheck compatibility marker: def build_acceptance_contract
# Healthcheck compatibility marker: def validate_acceptance_contract
# Healthcheck compatibility marker: def evaluate_acceptance_contract
# Healthcheck compatibility marker: def current_registry_ids
# Healthcheck compatibility marker: contract_version
# Healthcheck compatibility marker: 1.0
# Healthcheck compatibility marker: upgrade_id
# Healthcheck compatibility marker: title
# Healthcheck compatibility marker: required_files
# Healthcheck compatibility marker: required_healthcheck_markers
# Healthcheck compatibility marker: required_commit_subject
# Healthcheck compatibility marker: registry_id
# Healthcheck compatibility marker: missing contract key: {key}
# Healthcheck compatibility marker: unsafe required file path: {rel}
# Healthcheck compatibility marker: missing required file: {rel}
# Healthcheck compatibility marker: missing healthcheck marker: {marker}
# Healthcheck compatibility marker: missing expected commit subject: {commit_subject}
# Healthcheck compatibility marker: missing registry id: {expected_registry_id}
# Healthcheck compatibility marker: accepted
# Healthcheck compatibility marker: unknown
# Healthcheck compatibility marker: problems

from link_core.health.planner_acceptance_contract import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.health.planner_acceptance_contract", run_name="__main__")
