"""
Modern task runtime for link.

Inspired by modern CLI-agent task systems, but implemented from scratch in
plain Python for your local Ollama/vLLM workflow.

Adds:
- stable typed task statuses
- terminal-state guards
- short collision-resistant task IDs
- JSONL event stream for later replay/debugging
- per-task output files under .agents/tasks/
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import secrets
import string
from typing import Any, Iterable


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class TaskKind(str, Enum):
    MAIN = "main"
    EXPLORE = "explore"
    PLAN = "plan"
    BUILD = "build"
    TEST = "test"
    RCA = "rca"
    SHELL = "shell"
    AGENT = "agent"


TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED}
_ALPHABET = string.digits + string.ascii_lowercase
_PREFIX = {
    TaskKind.MAIN: "m",
    TaskKind.EXPLORE: "e",
    TaskKind.PLAN: "p",
    TaskKind.BUILD: "b",
    TaskKind.TEST: "t",
    TaskKind.RCA: "r",
    TaskKind.SHELL: "s",
    TaskKind.AGENT: "a",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_terminal(status: TaskStatus | str) -> bool:
    try:
        status = TaskStatus(status)
    except ValueError:
        return False
    return status in TERMINAL_STATUSES


def generate_task_id(kind: TaskKind | str) -> str:
    kind = TaskKind(kind)
    return _PREFIX.get(kind, "x") + "".join(secrets.choice(_ALPHABET) for _ in range(8))


@dataclass
class TaskRecord:
    id: str
    kind: TaskKind
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    output_file: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        if is_terminal(self.status):
            raise RuntimeError(f"cannot start terminal task {self.id}: {self.status}")
        self.status = TaskStatus.RUNNING
        self.started_at = self.started_at or utc_now()

    def finish(self, status: TaskStatus | str, **metadata: Any) -> None:
        status = TaskStatus(status)
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"finish() requires terminal status, got {status}")
        self.status = status
        self.ended_at = utc_now()
        self.metadata.update(metadata)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["status"] = self.status.value
        return data


class TaskStore:
    def __init__(self, working_dir: Path):
        self.root = Path(working_dir) / ".agents" / "tasks"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "events.jsonl"
        self.records: dict[str, TaskRecord] = {}

    def output_path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.out"

    def emit(self, event: str, task: TaskRecord, **payload: Any) -> None:
        row = {"ts": utc_now(), "event": event, "task": task.to_json(), **payload}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def create(self, kind: TaskKind | str, description: str, **metadata: Any) -> TaskRecord:
        kind = TaskKind(kind)
        task = TaskRecord(
            id=generate_task_id(kind),
            kind=kind,
            description=description,
            output_file=str(self.output_path(generate_task_id(kind))),
            metadata=dict(metadata),
        )
        # Fix output_file to same generated id.
        task.output_file = str(self.output_path(task.id))
        self.records[task.id] = task
        self.emit("created", task)
        return task

    def start(self, task_id: str) -> TaskRecord:
        task = self.records[task_id]
        task.start()
        self.emit("started", task)
        return task

    def finish(self, task_id: str, status: TaskStatus | str, **metadata: Any) -> TaskRecord:
        task = self.records[task_id]
        task.finish(status, **metadata)
        self.emit("finished", task)
        return task

    def active(self) -> list[TaskRecord]:
        return [t for t in self.records.values() if not is_terminal(t.status)]

    def background_summary(self) -> str:
        active = self.active()
        if not active:
            return "no active tasks"
        return ", ".join(f"{t.id}:{t.kind.value}:{t.status.value}" for t in active)
