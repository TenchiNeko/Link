#!/usr/bin/env python3
"""Deterministic dead-code audit helpers for Link.

Audit-only. This module does not delete files, move files, edit files, or touch git.
It identifies likely junk/dead-code signals so cleanup can happen intentionally later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast


SKIP_DIRS = {
    ".git",
    ".agents",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "research",
}

REMOVED_JUNK_NAMES = {
    "sub" + "conscious-daemon",
    "split_consciousness.py",
    "consciousness_dashboard.py",
    "consciousness_dashboard1.py",
    "consciousness_integration.py",
    "kb_client.py",
    "librarian.py",
    "librarian_store.py",
}

FORBIDDEN_IMPORT_MODULES = {
    "kb_client",
    "librarian",
    "librarian_store",
    "consciousness_integration",
    "fran" + "cesca_idle_trainer",
}

# Known transitional compatibility imports. These are still cleanup candidates,
# but they are optional/fallback guarded and should not fail the healthcheck.
LEGACY_OPTIONAL_IMPORT_ALLOWLIST = {
    ("standalone_orchestrator.py", "kb_client"),
    ("standalone_orchestrator.py", "librarian"),
    ("standalone_orchestrator.py", "librarian_store"),
    ("standalone_orchestrator.py", "consciousness_integration"),
}


@dataclass(frozen=True)
class DeadCodeFinding:
    path: str
    kind: str
    detail: str


def _should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return any(part in SKIP_DIRS for part in rel.parts)


def find_removed_junk_present(root: Path) -> list[DeadCodeFinding]:
    findings: list[DeadCodeFinding] = []
    for name in sorted(REMOVED_JUNK_NAMES):
        candidate = root / name
        if candidate.exists():
            findings.append(
                DeadCodeFinding(
                    path=name,
                    kind="removed_junk_present",
                    detail="previously removed junk exists in Link root",
                )
            )
    return findings


def _finding_kind_for_import(rel: str, module: str) -> str:
    base = module.split(".", 1)[0]
    if (rel, base) in LEGACY_OPTIONAL_IMPORT_ALLOWLIST:
        return "legacy_optional_import"
    return "forbidden_import"


def find_forbidden_imports(root: Path) -> list[DeadCodeFinding]:
    findings: list[DeadCodeFinding] = []

    for path in sorted(root.rglob("*.py")):
        if _should_skip(path, root):
            continue

        rel = str(path.relative_to(root))

        try:
            tree = ast.parse(path.read_text(errors="ignore"))
        except SyntaxError as exc:
            findings.append(DeadCodeFinding(rel, "syntax_error", str(exc)))
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".", 1)[0]
                    if base in FORBIDDEN_IMPORT_MODULES:
                        findings.append(
                            DeadCodeFinding(
                                rel,
                                _finding_kind_for_import(rel, alias.name),
                                f"imports {alias.name}",
                            )
                        )

            if isinstance(node, ast.ImportFrom):
                if node.module:
                    base = node.module.split(".", 1)[0]
                    if base in FORBIDDEN_IMPORT_MODULES:
                        findings.append(
                            DeadCodeFinding(
                                rel,
                                _finding_kind_for_import(rel, node.module),
                                f"from {node.module} import ...",
                            )
                        )

    return findings


def find_top_level_junk_candidates(root: Path) -> list[DeadCodeFinding]:
    findings: list[DeadCodeFinding] = []

    junk_suffixes = {
        ".bak",
        ".old",
        ".orig",
        ".tmp",
        ".swp",
    }

    junk_names = {
        ".DS_Store",
    }

    for path in sorted(root.iterdir()):
        if path.name in SKIP_DIRS:
            continue

        if path.name in junk_names or path.suffix in junk_suffixes:
            findings.append(
                DeadCodeFinding(
                    path.name,
                    "top_level_junk_candidate",
                    "backup/temp/metadata-looking file in Link root",
                )
            )

    return findings


def run_dead_code_audit(root: Path) -> list[DeadCodeFinding]:
    root = root.resolve()
    findings: list[DeadCodeFinding] = []
    findings.extend(find_removed_junk_present(root))
    findings.extend(find_forbidden_imports(root))
    findings.extend(find_top_level_junk_candidates(root))
    return findings


def format_dead_code_audit(findings: list[DeadCodeFinding]) -> str:
    if not findings:
        return "Dead-code audit: no high-confidence junk findings."

    lines = ["Dead-code audit findings:"]
    for finding in findings:
        lines.append(f"- [{finding.kind}] {finding.path}: {finding.detail}")
    return "\n".join(lines)
