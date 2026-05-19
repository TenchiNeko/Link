"""
Tiny AST symbol index for Python projects.

Use this before prompts so local models see callable/class signatures instead
of giant pasted files. It is intentionally stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import ast
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Symbol:
    file: str
    kind: str
    name: str
    line: int
    signature: str


def _signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = []
        for a in node.args.args:
            args.append(a.arg)
        if node.args.vararg:
            args.append("*" + node.args.vararg.arg)
        for a in node.args.kwonlyargs:
            args.append(a.arg)
        if node.args.kwarg:
            args.append("**" + node.args.kwarg.arg)
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)})"
    if isinstance(node, ast.ClassDef):
        bases = [getattr(b, "id", getattr(b, "attr", "?")) for b in node.bases]
        return f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")
    return ""


def index_file(path: Path, root: Path) -> list[Symbol]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[Symbol] = []
    rel = str(path.relative_to(root))
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(rel, node.__class__.__name__, node.name, getattr(node, "lineno", 0), _signature(node)))
    return sorted(out, key=lambda s: (s.file, s.line, s.name))


def build_index(root: Path, *, max_files: int = 500) -> list[Symbol]:
    symbols: list[Symbol] = []
    skip = {".git", ".agents", "venv", ".venv", "__pycache__", "node_modules", "backups", "ik_llama.cpp", "unsloth_compiled_cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", "consciousness-patch", "consciousness-v2", "consciousness-v3", "[private-name]_backup_20260423", "archive", "watermark_backups"}
    files = [p for p in root.rglob("*.py") if not any(part in skip for part in p.parts)]
    for path in sorted(files)[:max_files]:
        symbols.extend(index_file(path, root))
    return symbols


def render_symbol_context(root: Path, query: str = "", *, limit: int = 80) -> str:
    terms = {t.lower() for t in query.replace("_", " ").split() if len(t) > 2}
    symbols = build_index(root)
    if terms:
        ranked = []
        for s in symbols:
            blob = f"{s.file} {s.name} {s.signature}".lower()
            score = sum(1 for t in terms if t in blob)
            if score:
                ranked.append((score, s))
        symbols = [s for _, s in sorted(ranked, key=lambda x: (-x[0], x[1].file, x[1].line))]
    lines = ["# Symbol context"]
    for s in symbols[:limit]:
        lines.append(f"- {s.file}:{s.line} {s.signature}")
    return "\n".join(lines)

# Backward-compatible alias
build_symbol_index = build_index
