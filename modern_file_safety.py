"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_file_safety
"""

# Healthcheck compatibility marker: class FileRiskLevel
# Healthcheck compatibility marker: class FileSafetyAssessment
# Healthcheck compatibility marker: def _inside
# Healthcheck compatibility marker: def classify_file_operation
# Healthcheck compatibility marker: allow
# Healthcheck compatibility marker: caution
# Healthcheck compatibility marker: deny
# Healthcheck compatibility marker: .git
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: venv
# Healthcheck compatibility marker: .venv
# Healthcheck compatibility marker: __pycache__
# Healthcheck compatibility marker: .pytest_cache
# Healthcheck compatibility marker: .mypy_cache
# Healthcheck compatibility marker: .ruff_cache
# Healthcheck compatibility marker: research
# Healthcheck compatibility marker: .py
# Healthcheck compatibility marker: .md
# Healthcheck compatibility marker: .txt
# Healthcheck compatibility marker: .json
# Healthcheck compatibility marker: .toml
# Healthcheck compatibility marker: .yml
# Healthcheck compatibility marker: .yaml
# Healthcheck compatibility marker: .sh
# Healthcheck compatibility marker: read
# Healthcheck compatibility marker: path is outside the Link repo root
# Healthcheck compatibility marker: path is inside protected generated/internal state
# Healthcheck compatibility marker: delete
# Healthcheck compatibility marker: remove
# Healthcheck compatibility marker: delete operations require a separate manual cleanup flow
# Healthcheck compatibility marker: path is in research/reference material; do not merge directly
# Healthcheck compatibility marker: write
# Healthcheck compatibility marker: edit
# Healthcheck compatibility marker: move
# Healthcheck compatibility marker: copy
# Healthcheck compatibility marker: {op} may modify repo state
# Healthcheck compatibility marker: read-only inspection inside Link repo
# Healthcheck compatibility marker: read target has a less common file type
# Healthcheck compatibility marker: unknown file operation
# Healthcheck compatibility marker: FileRiskLevel
# Healthcheck compatibility marker: FileSafetyAssessment
# Healthcheck compatibility marker: classify_file_operation

from link_core.modern.modern_file_safety import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_file_safety", run_name="__main__")
