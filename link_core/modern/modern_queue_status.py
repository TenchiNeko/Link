#!/usr/bin/env python3
"""Deterministic queue/status helpers for Link.

Small, dependency-free status layer for future background jobs.
This module does not run agents, spawn processes, edit files, or touch git.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QueueStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELED = "canceled"


@dataclass(frozen=True)
class QueueItem:
    id: str
    title: str
    status: QueueStatus = QueueStatus.QUEUED
    detail: str = ""
    order: int = 0


_ACTIVE_STATUSES = {QueueStatus.QUEUED, QueueStatus.RUNNING}
_FAILURE_STATUSES = {QueueStatus.FAILED, QueueStatus.BLOCKED}


def summarize_queue(items: list[QueueItem]) -> dict[str, int]:
    counts = {status.value: 0 for status in QueueStatus}
    for item in items:
        counts[item.status.value] += 1
    counts["total"] = len(items)
    counts["active"] = sum(1 for item in items if item.status in _ACTIVE_STATUSES)
    counts["needs_attention"] = sum(1 for item in items if item.status in _FAILURE_STATUSES)
    return counts


def next_active_item(items: list[QueueItem]) -> QueueItem | None:
    active = [item for item in items if item.status in _ACTIVE_STATUSES]
    if not active:
        return None
    return sorted(active, key=lambda item: (item.status != QueueStatus.RUNNING, item.order, item.id))[0]


def format_queue_status(items: list[QueueItem]) -> str:
    summary = summarize_queue(items)
    lines = [
        "Link Queue Status",
        f"- total: {summary['total']}",
        f"- active: {summary['active']}",
        f"- needs_attention: {summary['needs_attention']}",
    ]

    current = next_active_item(items)
    if current is None:
        lines.append("- current: none")
    else:
        lines.append(f"- current: [{current.status.value}] {current.id} — {current.title}")

    for item in sorted(items, key=lambda entry: (entry.order, entry.id)):
        detail = f" — {item.detail}" if item.detail else ""
        lines.append(f"  - [{item.status.value}] {item.id}: {item.title}{detail}")

    return "\n".join(lines)


def validate_queue(items: list[QueueItem]) -> None:
    seen: set[str] = set()
    for item in items:
        if not item.id.strip():
            raise ValueError("queue item id cannot be empty")
        if item.id in seen:
            raise ValueError(f"duplicate queue item id: {item.id}")
        seen.add(item.id)
