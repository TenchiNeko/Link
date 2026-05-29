"""Canonical Link artifacts facade.

Import path: ``link_core.artifacts``

Artifacts are the durable evidence Link produces: execution receipts,
rollback/audit snapshots, and concise task receipts. This module is a thin
facade over the existing working modules:

- ``link_core.evidence.execution_receipts`` (signed execution receipts)
- ``link_core.evidence.execution_snapshots`` (read-only rollback snapshots)
- ``link_core.receipts.link_task_receipt`` (concise task receipts)

No behavior is changed here. Receipt creation is deterministic and
snapshot creation is read-only with respect to repository state.
"""

from __future__ import annotations

from link_core.evidence.execution_receipts import (
    build_execution_receipt,
    latest_receipts,
    verify_execution_receipt,
    write_execution_receipt,
)

# Snapshot creation depends on git safety classification; import defensively.
try:  # pragma: no cover - defensive import
    from link_core.evidence.execution_snapshots import create_execution_snapshot
except Exception:  # pragma: no cover
    create_execution_snapshot = None  # type: ignore[assignment]

# Concise task receipts depend on the task-patch planner; import defensively.
try:  # pragma: no cover - defensive import
    from link_core.receipts.link_task_receipt import (
        build_concise_task_receipt,
        render_concise_task_receipt,
    )
except Exception:  # pragma: no cover
    build_concise_task_receipt = None  # type: ignore[assignment]
    render_concise_task_receipt = None  # type: ignore[assignment]

__all__ = [
    # execution receipts
    "build_execution_receipt",
    "write_execution_receipt",
    "verify_execution_receipt",
    "latest_receipts",
    # snapshots
    "create_execution_snapshot",
    # task receipts
    "build_concise_task_receipt",
    "render_concise_task_receipt",
]
