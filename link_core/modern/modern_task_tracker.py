#!/usr/bin/env python3
"""Deterministic task/todo tracking helpers for Link.

Small, dependency-free planning layer for future Link improvements.
This module does not run agents, edit files, or touch git by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class TaskItem:
    id: str
    title: str
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.NORMAL
    notes: str = ""


@dataclass
class TaskBoard:
    items: list[TaskItem] = field(default_factory=list)


_PRIORITY_RANK = {
    TaskPriority.HIGH: 0,
    TaskPriority.NORMAL: 1,
    TaskPriority.LOW: 2,
}


def _clean_title(title: str) -> str:
    cleaned = " ".join((title or "").strip().split())
    if not cleaned:
        raise ValueError("task title cannot be empty")
    if len(cleaned) > 200:
        raise ValueError("task title is too long")
    return cleaned


def _coerce_status(status: TaskStatus | str) -> TaskStatus:
    if isinstance(status, TaskStatus):
        return status
    return TaskStatus(str(status))


def _coerce_priority(priority: TaskPriority | str) -> TaskPriority:
    if isinstance(priority, TaskPriority):
        return priority
    return TaskPriority(str(priority))


def add_task(
    board: TaskBoard,
    title: str,
    *,
    priority: TaskPriority | str = TaskPriority.NORMAL,
    notes: str = "",
) -> TaskItem:
    """Add one deterministic task to a board."""
    task = TaskItem(
        id=f"T{len(board.items) + 1:03d}",
        title=_clean_title(title),
        priority=_coerce_priority(priority),
        notes=(notes or "").strip(),
    )
    board.items.append(task)
    return task


def find_task(board: TaskBoard, task_id: str) -> TaskItem:
    for task in board.items:
        if task.id == task_id:
            return task
    raise KeyError(f"task not found: {task_id}")


def update_task_status(
    board: TaskBoard,
    task_id: str,
    status: TaskStatus | str,
    *,
    notes: str | None = None,
) -> TaskItem:
    task = find_task(board, task_id)
    task.status = _coerce_status(status)
    if notes is not None:
        task.notes = notes.strip()
    return task


def next_open_task(board: TaskBoard) -> TaskItem | None:
    """Return the highest-priority open task, preserving creation order."""
    open_tasks = [
        (index, task)
        for index, task in enumerate(board.items)
        if task.status not in {TaskStatus.DONE, TaskStatus.BLOCKED}
    ]
    if not open_tasks:
        return None
    return sorted(
        open_tasks,
        key=lambda pair: (_PRIORITY_RANK[pair[1].priority], pair[0]),
    )[0][1]


def summarize_board(board: TaskBoard) -> dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    for task in board.items:
        counts[task.status.value] += 1
    counts["total"] = len(board.items)
    counts["open"] = counts["todo"] + counts["doing"]
    return counts


def format_board(board: TaskBoard) -> str:
    if not board.items:
        return "No tasks."
    lines = []
    for task in board.items:
        lines.append(
            f"- [{task.status.value}] {task.id} {task.priority.value}: {task.title}"
        )
    return "\n".join(lines)
