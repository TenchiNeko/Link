"""
Safer edit helpers for agent mutations.

Adds:
- unified-diff application
- function/class replacement by AST span
- post-edit Python syntax validation
"""
from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditResult:
    ok: bool
    message: str
    new_content: str | None = None


def validate_python(path: Path, content: str) -> EditResult:
    if path.suffix != ".py":
        return EditResult(True, "not python")
    try:
        ast.parse(content)
        return EditResult(True, "syntax ok")
    except SyntaxError as e:
        return EditResult(False, f"SyntaxError line {e.lineno}: {e.msg}")


def apply_unified_diff(original: str, patch: str) -> EditResult:
    """
    Minimal stdlib unified-diff applier.
    Expects one-file unified diffs from difflib/unified_diff style.
    """
    lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    out: list[str] = []
    src_i = 0
    p_i = 0

    while p_i < len(patch_lines):
        line = patch_lines[p_i]
        if line.startswith("--- ") or line.startswith("+++ "):
            p_i += 1
            continue
        if not line.startswith("@@ "):
            p_i += 1
            continue

        header = line
        try:
            old_part = header.split(" ")[1]
            old_start = int(old_part.split(",")[0][1:])
        except Exception:
            return EditResult(False, f"bad diff hunk header: {header.strip()}")

        hunk_start = max(old_start - 1, 0)
        out.extend(lines[src_i:hunk_start])
        src_i = hunk_start
        p_i += 1

        while p_i < len(patch_lines) and not patch_lines[p_i].startswith("@@ "):
            h = patch_lines[p_i]
            if h.startswith(" "):
                expected = h[1:]
                if src_i >= len(lines) or lines[src_i] != expected:
                    return EditResult(False, "diff context mismatch")
                out.append(lines[src_i])
                src_i += 1
            elif h.startswith("-"):
                expected = h[1:]
                if src_i >= len(lines) or lines[src_i] != expected:
                    return EditResult(False, "diff removal mismatch")
                src_i += 1
            elif h.startswith("+"):
                out.append(h[1:])
            elif h.startswith("\\"):
                pass
            p_i += 1

    out.extend(lines[src_i:])
    return EditResult(True, "diff applied", "".join(out))


def replace_symbol(content: str, symbol_name: str, replacement: str) -> EditResult:
    tree = ast.parse(content)
    lines = content.splitlines(keepends=True)

    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol_name:
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                matches.append(node)

    if not matches:
        return EditResult(False, f"symbol not found: {symbol_name}")
    if len(matches) > 1:
        return EditResult(False, f"symbol is ambiguous: {symbol_name} appears {len(matches)} times")

    node = matches[0]
    start = node.lineno - 1
    end = node.end_lineno

    if not replacement.endswith("\n"):
        replacement += "\n"

    new_content = "".join(lines[:start]) + replacement + "".join(lines[end:])
    return EditResult(True, f"replaced symbol: {symbol_name}", new_content)


def make_diff(old: str, new: str, filename: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )
