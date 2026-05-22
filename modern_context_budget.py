#!/usr/bin/env python3
"""Deterministic context budget and compaction helpers for Link.

Small, dependency-free helpers for estimating prompt size and trimming context.
This module does not call models, edit files, or mutate runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContextPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass(frozen=True)
class ContextBlock:
    id: str
    title: str
    text: str
    priority: ContextPriority = ContextPriority.NORMAL


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int
    reserve_tokens: int = 512
    chars_per_token: int = 4


@dataclass(frozen=True)
class CompactedContext:
    text: str
    estimated_tokens: int
    omitted_blocks: list[str]
    truncated_blocks: list[str]


_PRIORITY_RANK = {
    ContextPriority.HIGH: 0,
    ContextPriority.NORMAL: 1,
    ContextPriority.LOW: 2,
}


def estimate_tokens(text: str, *, chars_per_token: int = 4) -> int:
    """Deterministic rough token estimate.

    Intentionally conservative enough for planning without requiring tokenizer deps.
    """
    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive")
    text = text or ""
    return max(1, (len(text) + chars_per_token - 1) // chars_per_token)


def usable_token_budget(budget: ContextBudget) -> int:
    usable = budget.max_tokens - budget.reserve_tokens
    if usable <= 0:
        raise ValueError("reserve_tokens must be smaller than max_tokens")
    return usable


def trim_text(text: str, max_tokens: int, *, chars_per_token: int = 4) -> tuple[str, bool]:
    """Trim text to a rough token budget while preserving head and tail context."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")

    text = text or ""
    max_chars = max_tokens * chars_per_token

    if len(text) <= max_chars:
        return text, False

    marker = "\n\n[...context omitted...]\n\n"
    available = max(0, max_chars - len(marker))

    if available <= 0:
        return text[:max_chars], True

    head_chars = max(1, int(available * 0.65))
    tail_chars = max(1, available - head_chars)

    return text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip(), True


def compact_blocks(blocks: list[ContextBlock], budget: ContextBudget) -> CompactedContext:
    """Return deterministic compacted context within the usable token budget.

    Higher-priority blocks are considered first. Creation order is preserved inside
    the same priority level.
    """
    usable_tokens = usable_token_budget(budget)
    remaining_tokens = usable_tokens

    ordered = sorted(
        enumerate(blocks),
        key=lambda pair: (_PRIORITY_RANK[pair[1].priority], pair[0]),
    )

    included: list[str] = []
    omitted: list[str] = []
    truncated: list[str] = []

    for _, block in ordered:
        header = f"## {block.title}\n"
        block_text = header + (block.text or "").strip() + "\n"
        needed = estimate_tokens(block_text, chars_per_token=budget.chars_per_token)

        if needed <= remaining_tokens:
            included.append(block_text)
            remaining_tokens -= needed
            continue

        if remaining_tokens >= 64:
            trimmed, was_trimmed = trim_text(
                block_text,
                remaining_tokens,
                chars_per_token=budget.chars_per_token,
            )
            included.append(trimmed.rstrip() + "\n")
            if was_trimmed:
                truncated.append(block.id)
            remaining_tokens = 0
        else:
            omitted.append(block.id)

    compacted = "\n".join(included).strip()
    return CompactedContext(
        text=compacted,
        estimated_tokens=estimate_tokens(
            compacted,
            chars_per_token=budget.chars_per_token,
        ),
        omitted_blocks=omitted,
        truncated_blocks=truncated,
    )


def summarize_budget_result(result: CompactedContext) -> dict[str, object]:
    return {
        "estimated_tokens": result.estimated_tokens,
        "omitted_blocks": list(result.omitted_blocks),
        "truncated_blocks": list(result.truncated_blocks),
        "has_text": bool(result.text.strip()),
    }


# === LU01 context/truncation hardening ===
def estimate_context_tokens_from_chars(total_chars: int) -> int:
    """Small deterministic char→token estimate used for manifest budgeting."""
    return max(0, int((int(total_chars or 0) + 3) // 4))

def get_context_budget_summary(content=None, files=None, total_chars=None, total_tokens_est=None) -> dict:
    """
    Normalize context budget data for context manifests.

    Accepts raw content, file records, or explicit totals.
    Returns: {"total_chars": int, "total_tokens_est": int}
    """
    if total_chars is None:
        if content is not None:
            total_chars = len(str(content))
        elif files is not None:
            total_chars = 0
            for f in files:
                if isinstance(f, dict):
                    total_chars += int(f.get("size_bytes", f.get("chars", 0)) or 0)
                else:
                    total_chars += len(str(f))
        else:
            total_chars = 0

    if total_tokens_est is None:
        total_tokens_est = estimate_context_tokens_from_chars(int(total_chars or 0))

    return {
        "total_chars": int(total_chars or 0),
        "total_tokens_est": int(total_tokens_est or 0),
    }
# === end LU01 context/truncation hardening ===

