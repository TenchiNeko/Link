#!/usr/bin/env python3
"""Small deterministic schema helpers for Growth.

This module is intentionally narrow. It owns only mechanical normalization
helpers that are shared across extracted Growth modules. CLI dispatch and
payload-specific schema families stay in link_growth_console.py.
"""

from __future__ import annotations

from typing import Any


def read_only_safety_metadata() -> dict[str, Any]:
    return {
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "writes": [],
    }


def normalized_non_empty_keys(*values: Any) -> list[str]:
    keys: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in keys:
            keys.append(text)
    return keys


def normalize_implementation_branch_refs(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        raise TypeError("implementation branch refs must be a string or list")
    normalized: list[str] = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError("implementation branch refs cannot contain empty strings")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid implementation branch ref: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)
