#!/usr/bin/env python3
"""Audit remaining runtime legacy references.

Audit-only. This script does not delete, move, edit, import legacy modules,
run agents, or touch git. It scans runtime Python files and writes a redacted
Markdown report that remains compatible with link_healthcheck.py.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import datetime


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "RUNTIME_LEGACY_AUDIT.md"

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

SKIP_FILES = {
    "RUNTIME_LEGACY_AUDIT.md",
    "LINK_RECOVERY_DECISIONS.md",
    "link_healthcheck.py",
    "runtime_legacy_audit.py",
    "modern_dead_code_audit.py",
}

SCAN_SUFFIXES = {".py"}


@dataclass(frozen=True)
class LegacyPattern:
    label: str
    needle: str
    severity: str


@dataclass(frozen=True)
class Finding:
    severity: str
    label: str
    file: str
    line: int
    snippet: str


PATTERNS = [
    LegacyPattern("external_project_alpha_ref", "fran" + "cesca", "medium"),
    LegacyPattern("external_project_beta_ref", "fan" + "vue", "medium"),
    LegacyPattern("external_trainer_ref", "fran" + "cesca_idle_trainer", "medium"),
    LegacyPattern("old_daemon_ref", "sub" + "conscious-daemon", "medium"),
    LegacyPattern("old_kb_import", "from " + "kb_client", "high"),
    LegacyPattern("old_library_import", "from " + "librarian import", "high"),
    LegacyPattern("old_library_store_import", "from " + "librarian_store", "high"),
    LegacyPattern("old_layer_import", "from " + "consciousness_integration", "high"),
]


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if path.name in SKIP_FILES:
        return True
    if path.suffix not in SCAN_SUFFIXES:
        return True
    return any(part in SKIP_DIRS for part in rel.parts)


def redact(text: str) -> str:
    redacted = text.strip()
    for pattern in PATTERNS:
        redacted = redacted.replace(pattern.needle, f"<{pattern.label}>")
    return redacted.replace("|", "\\|")


def scan() -> list[Finding]:
    findings: list[Finding] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or should_skip(path):
            continue

        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue

        for line_no, line in enumerate(lines, start=1):
            for pattern in PATTERNS:
                if pattern.needle.lower() in line.lower():
                    findings.append(
                        Finding(
                            severity=pattern.severity,
                            label=pattern.label,
                            file=rel,
                            line=line_no,
                            snippet=redact(line),
                        )
                    )

    return findings


def write_report(findings: list[Finding]) -> None:
    counts = Counter(f.label for f in findings)

    out: list[str] = [
        "# Runtime Legacy Audit",
        "",
        f"- Created: {datetime.datetime.now().replace(microsecond=0).isoformat()}",
        f"- Repo: `{ROOT}`",
        "- Mode: audit-only, no cleanup performed",
        "- Scope: runtime Python files only; safety docs and audit helpers are excluded.",
        "- Note: matched strings are intentionally redacted so the report stays healthcheck-safe.",
        "",
        "## Summary",
        "",
        f"- Total findings: {len(findings)}",
    ]

    for label, count in sorted(counts.items()):
        out.append(f"- {label}: {count}")

    out.extend(
        [
            "",
            "## Findings",
            "",
            "| Severity | Label | File | Line | Redacted snippet |",
            "|---|---|---:|---:|---|",
        ]
    )

    for finding in findings:
        out.append(
            f"| {finding.severity} | {finding.label} | `{finding.file}` | "
            f"{finding.line} | `{finding.snippet}` |"
        )

    out.extend(
        [
            "",
            "## Recommended next step",
            "",
            "Review remaining runtime findings. Remove one tiny legacy reference at a time, then run `python3 link_healthcheck.py` before committing.",
            "",
        ]
    )

    REPORT.write_text("\n".join(out))


def main() -> None:
    findings = scan()
    write_report(findings)
    print(f"wrote {REPORT}")
    print(f"findings: {len(findings)}")


if __name__ == "__main__":
    main()
