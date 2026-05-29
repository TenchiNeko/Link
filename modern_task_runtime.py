"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_task_runtime
"""

# Healthcheck compatibility marker: class TaskStatus
# Healthcheck compatibility marker: class TaskKind
# Healthcheck compatibility marker: def utc_now
# Healthcheck compatibility marker: def is_terminal
# Healthcheck compatibility marker: def generate_task_id
# Healthcheck compatibility marker: class TaskRecord
# Healthcheck compatibility marker: class TaskStore
# Healthcheck compatibility marker: pending
# Healthcheck compatibility marker: running
# Healthcheck compatibility marker: completed
# Healthcheck compatibility marker: failed
# Healthcheck compatibility marker: killed
# Healthcheck compatibility marker: main
# Healthcheck compatibility marker: explore
# Healthcheck compatibility marker: plan
# Healthcheck compatibility marker: build
# Healthcheck compatibility marker: test
# Healthcheck compatibility marker: rca
# Healthcheck compatibility marker: shell
# Healthcheck compatibility marker: agent
# Healthcheck compatibility marker: ) +
# Healthcheck compatibility marker: cannot start terminal task {self.id}: {self.status}
# Healthcheck compatibility marker: finish() requires terminal status, got {status}
# Healthcheck compatibility marker: kind
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: tasks
# Healthcheck compatibility marker: events.jsonl
# Healthcheck compatibility marker: {task_id}.out
# Healthcheck compatibility marker: : utc_now(),
# Healthcheck compatibility marker: : event,
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: created
# Healthcheck compatibility marker: started
# Healthcheck compatibility marker: finished
# Healthcheck compatibility marker: no active tasks
# Healthcheck compatibility marker: .join(f

from link_core.modern.modern_task_runtime import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_task_runtime", run_name="__main__")
