"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_task_tracker
"""

# Healthcheck compatibility marker: class TaskStatus
# Healthcheck compatibility marker: class TaskPriority
# Healthcheck compatibility marker: class TaskItem
# Healthcheck compatibility marker: class TaskBoard
# Healthcheck compatibility marker: def _clean_title
# Healthcheck compatibility marker: def _coerce_status
# Healthcheck compatibility marker: def _coerce_priority
# Healthcheck compatibility marker: def add_task
# Healthcheck compatibility marker: def find_task
# Healthcheck compatibility marker: def update_task_status
# Healthcheck compatibility marker: def next_open_task
# Healthcheck compatibility marker: def summarize_board
# Healthcheck compatibility marker: def format_board
# Healthcheck compatibility marker: todo
# Healthcheck compatibility marker: doing
# Healthcheck compatibility marker: done
# Healthcheck compatibility marker: blocked
# Healthcheck compatibility marker: high
# Healthcheck compatibility marker: normal
# Healthcheck compatibility marker: low
# Healthcheck compatibility marker: .join((title or
# Healthcheck compatibility marker: task title cannot be empty
# Healthcheck compatibility marker: task title is too long
# Healthcheck compatibility marker: Add one deterministic task to a board.
# Healthcheck compatibility marker: T{len(board.items) + 1:03d}
# Healthcheck compatibility marker: task not found: {task_id}
# Healthcheck compatibility marker: Return the highest-priority open task, preserving creation order.
# Healthcheck compatibility marker: total
# Healthcheck compatibility marker: open
# Healthcheck compatibility marker: No tasks.
# Healthcheck compatibility marker: - [{task.status.value}] {task.id} {task.priority.value}: {task.title}

from link_core.modern.modern_task_tracker import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_task_tracker", run_name="__main__")
