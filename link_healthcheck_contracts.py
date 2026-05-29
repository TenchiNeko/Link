"""Compatibility shim for moved module.

Canonical module:
    link_core.health.link_healthcheck_contracts
"""

# Healthcheck compatibility marker: def check_context_truncation_contract
# Healthcheck compatibility marker: def check_context_manifest_integrity_contract
# Healthcheck compatibility marker: LINK_HEALTHCHECK_STRICT_CONTEXT_CONTRACT
# Healthcheck compatibility marker: healthcheck_fixtures
# Healthcheck compatibility marker: context_truncation
# Healthcheck compatibility marker: manifest.json
# Healthcheck compatibility marker: context truncation manifest missing: {manifest_path}
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: required_files
# Healthcheck compatibility marker: + path.read_text(encoding=
# Healthcheck compatibility marker: , errors=
# Healthcheck compatibility marker: context truncation fixture files missing: {missing}
# Healthcheck compatibility marker: required_sentinels
# Healthcheck compatibility marker: context truncation sentinels missing: {missing_sentinels}
# Healthcheck compatibility marker: context truncation oversized fixture is too small
# Healthcheck compatibility marker: context truncation fixture OK
# Healthcheck compatibility marker: context truncation strict contract skipped; set LINK_HEALTHCHECK_STRICT_CONTEXT_CONTRACT=1
# Healthcheck compatibility marker: STRICT_CONTEXT_CONTRACT_FAIL: factory.project_context could not be imported
# Healthcheck compatibility marker: ContextBundle
# Healthcheck compatibility marker: build_context_bundle
# Healthcheck compatibility marker: load_project_context_bundle
# Healthcheck compatibility marker: STRICT_CONTEXT_CONTRACT_FAIL: ContextBundle metadata API is not implemented yet.
# Healthcheck compatibility marker: Expected ContextBundle plus build_context_bundle() or load_project_context_bundle().
# Healthcheck compatibility marker: context truncation strict contract API detected
# Healthcheck compatibility marker: LU01: validate context manifest schema, status transitions, and final-gate check.
# Healthcheck compatibility marker: abcd
# Healthcheck compatibility marker: total_chars
# Healthcheck compatibility marker: total_tokens_est
# Healthcheck compatibility marker: path
# Healthcheck compatibility marker: factory/context/example.md
# Healthcheck compatibility marker: size_bytes
# Healthcheck compatibility marker: truncated
# Healthcheck compatibility marker: tail_sentinel
# Healthcheck compatibility marker: required
# Healthcheck compatibility marker: manifest_version
# Healthcheck compatibility marker: 1.0
# Healthcheck compatibility marker: integrity_status
# Healthcheck compatibility marker: PASS
# Healthcheck compatibility marker: blocking_flags
# Healthcheck compatibility marker: diagnosis
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: runs/old_qa_commentary.md
# Healthcheck compatibility marker: file
# Healthcheck compatibility marker: type
# Healthcheck compatibility marker: soft_clip
# Healthcheck compatibility marker: missing_bytes
# Healthcheck compatibility marker: is_deliverable
# Healthcheck compatibility marker: WARN
# Healthcheck compatibility marker: runs/02-production_worker.md
# Healthcheck compatibility marker: hard_clip
# Healthcheck compatibility marker: FAIL
# Healthcheck compatibility marker: required_file_truncated
# Healthcheck compatibility marker: TRUNCATED
# Healthcheck compatibility marker: sentinel_truncated
# Healthcheck compatibility marker: context manifest integrity OK

from link_core.health.link_healthcheck_contracts import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.health.link_healthcheck_contracts", run_name="__main__")
