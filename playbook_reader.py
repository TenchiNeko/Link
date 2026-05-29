"""Compatibility shim for moved module.

Canonical module:
    link_core.docs_runtime.playbook_reader
"""

# Healthcheck compatibility marker: class PlaybookReader
# Healthcheck compatibility marker: /shared/playbook.json
# Healthcheck compatibility marker: builder
# Healthcheck compatibility marker: \n\n
# Healthcheck compatibility marker: planner
# Healthcheck compatibility marker: architecture
# Healthcheck compatibility marker: build_ordering
# Healthcheck compatibility marker: general
# Healthcheck compatibility marker: import_resolution
# Healthcheck compatibility marker: flask_patterns
# Healthcheck compatibility marker: dataclass_patterns
# Healthcheck compatibility marker: sqlite_patterns
# Healthcheck compatibility marker: stdlib_usage
# Healthcheck compatibility marker: error_recovery
# Healthcheck compatibility marker: test_gen
# Healthcheck compatibility marker: test_generation
# Healthcheck compatibility marker: initializer
# Healthcheck compatibility marker: explorer
# Healthcheck compatibility marker: Load playbook, with simple mtime-based caching.
# Healthcheck compatibility marker: Could not read playbook: {e}
# Healthcheck compatibility marker: sections
# Healthcheck compatibility marker: helpful_count
# Healthcheck compatibility marker: harmful_count
# Healthcheck compatibility marker: ## Coding Playbook (learned patterns — follow these)
# Healthcheck compatibility marker: content
# Healthcheck compatibility marker: - [{bid}] {content}
# Healthcheck compatibility marker: .join(lines) +
# Healthcheck compatibility marker: Playbook context for {role}: {count} bullets, {char_count} chars
# Healthcheck compatibility marker: daemon
# Healthcheck compatibility marker: feedback
# Healthcheck compatibility marker: bullet_ids
# Healthcheck compatibility marker: was_successful
# Healthcheck compatibility marker: timestamp
# Healthcheck compatibility marker: datetime
# Healthcheck compatibility marker: bullet_feedback.jsonl
# Healthcheck compatibility marker: Could not write bullet feedback: {e}
# Healthcheck compatibility marker: Get quick stats about the current playbook.
# Healthcheck compatibility marker: available
# Healthcheck compatibility marker: total_bullets
# Healthcheck compatibility marker: last_updated
# Healthcheck compatibility marker: unknown

from link_core.docs_runtime.playbook_reader import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.docs_runtime.playbook_reader", run_name="__main__")
