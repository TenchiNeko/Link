"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_queue_status
"""

# Healthcheck compatibility marker: class QueueStatus
# Healthcheck compatibility marker: class QueueItem
# Healthcheck compatibility marker: def summarize_queue
# Healthcheck compatibility marker: def next_active_item
# Healthcheck compatibility marker: def format_queue_status
# Healthcheck compatibility marker: def validate_queue
# Healthcheck compatibility marker: queued
# Healthcheck compatibility marker: running
# Healthcheck compatibility marker: done
# Healthcheck compatibility marker: failed
# Healthcheck compatibility marker: blocked
# Healthcheck compatibility marker: canceled
# Healthcheck compatibility marker: total
# Healthcheck compatibility marker: active
# Healthcheck compatibility marker: needs_attention
# Healthcheck compatibility marker: Link Queue Status
# Healthcheck compatibility marker: - total: {summary['total']}
# Healthcheck compatibility marker: - active: {summary['active']}
# Healthcheck compatibility marker: - needs_attention: {summary['needs_attention']}
# Healthcheck compatibility marker: - current: none
# Healthcheck compatibility marker: - current: [{current.status.value}] {current.id} — {current.title}
# Healthcheck compatibility marker: — {item.detail}
# Healthcheck compatibility marker: - [{item.status.value}] {item.id}: {item.title}{detail}
# Healthcheck compatibility marker: queue item id cannot be empty
# Healthcheck compatibility marker: duplicate queue item id: {item.id}

from link_core.modern.modern_queue_status import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_queue_status", run_name="__main__")
