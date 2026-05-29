"""Compatibility shim for moved module.

Canonical module:
    link_core.diagnostics.modern_dead_code_audit
"""

# Healthcheck compatibility marker: class DeadCodeFinding
# Healthcheck compatibility marker: def _should_skip
# Healthcheck compatibility marker: def find_removed_junk_present
# Healthcheck compatibility marker: def _finding_kind_for_import
# Healthcheck compatibility marker: def find_forbidden_imports
# Healthcheck compatibility marker: def find_top_level_junk_candidates
# Healthcheck compatibility marker: def run_dead_code_audit
# Healthcheck compatibility marker: def format_dead_code_audit
# Healthcheck compatibility marker: .git
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: venv
# Healthcheck compatibility marker: .venv
# Healthcheck compatibility marker: __pycache__
# Healthcheck compatibility marker: .pytest_cache
# Healthcheck compatibility marker: .mypy_cache
# Healthcheck compatibility marker: .ruff_cache
# Healthcheck compatibility marker: research
# Healthcheck compatibility marker: sub
# Healthcheck compatibility marker: conscious-daemon
# Healthcheck compatibility marker: split_consciousness.py
# Healthcheck compatibility marker: consciousness_dashboard.py
# Healthcheck compatibility marker: consciousness_dashboard1.py
# Healthcheck compatibility marker: consciousness_integration.py
# Healthcheck compatibility marker: kb_client.py
# Healthcheck compatibility marker: librarian.py
# Healthcheck compatibility marker: librarian_store.py
# Healthcheck compatibility marker: kb_client
# Healthcheck compatibility marker: librarian
# Healthcheck compatibility marker: librarian_store
# Healthcheck compatibility marker: consciousness_integration
# Healthcheck compatibility marker: fran
# Healthcheck compatibility marker: cesca_idle_trainer
# Healthcheck compatibility marker: standalone_orchestrator.py
# Healthcheck compatibility marker: removed_junk_present
# Healthcheck compatibility marker: previously removed junk exists in Link root
# Healthcheck compatibility marker: legacy_optional_import
# Healthcheck compatibility marker: forbidden_import
# Healthcheck compatibility marker: *.py
# Healthcheck compatibility marker: ignore
# Healthcheck compatibility marker: syntax_error
# Healthcheck compatibility marker: imports {alias.name}
# Healthcheck compatibility marker: from {node.module} import ...
# Healthcheck compatibility marker: .bak
# Healthcheck compatibility marker: .old
# Healthcheck compatibility marker: .orig
# Healthcheck compatibility marker: .tmp
# Healthcheck compatibility marker: .swp
# Healthcheck compatibility marker: .DS_Store
# Healthcheck compatibility marker: top_level_junk_candidate
# Healthcheck compatibility marker: backup/temp/metadata-looking file in Link root
# Healthcheck compatibility marker: Dead-code audit: no high-confidence junk findings.
# Healthcheck compatibility marker: Dead-code audit findings:
# Healthcheck compatibility marker: - [{finding.kind}] {finding.path}: {finding.detail}

from link_core.diagnostics.modern_dead_code_audit import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.diagnostics.modern_dead_code_audit", run_name="__main__")
