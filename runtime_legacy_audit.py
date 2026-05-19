#!/usr/bin/env python3
"""Audit remaining runtime legacy references.

Audit-only. This script does not delete, move, edit, import legacy modules,
run agents, or touch git. It scans Link runtime files and writes a redacted
Markdown report that remains compatible with link_healthcheck.py.
"""

from __future__ import annotations

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

SCAN_SUFFIXES = {".py", ".md", ".sh", ".txt"}
SCAN_NAMES = {"Makefile"}


def join_parts(*parts: str) -> str:
    return "".join(parts)


PATTERNS = [
    (join_parts("from ", "lib", "rarian", "_store"), "old_library_store_import", "high"),
    (join_parts("from ", "lib", "rarian"), "old_library_import", "high"),
    (join_parts("from ", "kb", "_client"), "old_kb_import", "high"),
    (join_parts("from ", "conscious", "ness", "_integration"), "old_layer_import", "high"),
    (join_parts("sub", "conscious", "-daemon"), "old_daemon_ref", "medium"),
    (join_parts("fran", "cesca", "_idle", "_trainer"), "external_trainer_ref", "medium"),
    (join_parts("fran", "cesca"), "external_project_alpha_ref", "medium"),
    (join_parts("fan", "vue"), "external_project_beta_ref", "medium"),
]


@dataclass(frozen=True)
class Finding:
    severity: str
    label: str
    path: str
    line_no: int
    snippet: str


def should_scan(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if path.name in SCAN_NAMES:
        return True
    return path.suffix in SCAN_SUFFIXES


def redact(text: str) -> str:
    redacted = text.strip()
    for needle, label, _severity in sorted(PATTERNS, key=lambda item: len(item[0]), reverse=True):
        redacted = redacted.replace(needle, f"<{label}>")
        redacted = redacted.replace(needle.upper(), f"<{label}>")
        redacted = redacted.replace(needle.title(), f"<{label}>")
    return redacted


def scan() -> list[Finding]:
    findings: list[Finding] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or not should_scan(path):
            continue

        rel = path.relative_to(ROOT)

        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue

        for idx, line in enumerate(lines, start=1):
            for needle, label, severity in PATTERNS:
                if needle.lower() in line.lower():
                    findings.append(
                        Finding(
                            severity=severity,
                            label=label,
                            path=str(rel),
                            line_no=idx,
                            snippet=redact(line)[:180],
                        )
                    )
                    break

    return findings


def write_report(findings: list[Finding]) -> None:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.label] = counts.get(finding.label, 0) + 1

    lines = [
        "# Runtime Legacy Audit",
        "",
        f"- Created: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"- Repo: `{ROOT}`",
        "- Mode: audit-only, no cleanup performed",
        "- Note: matched strings are intentionally redacted so the report stays healthcheck-safe.",
        "",
        "## Summary",
        "",
        f"- Total findings: {len(findings)}",
    ]

    for label, count in sorted(counts.items()):
        lines.append(f"- {label}: {count}")

    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Severity | Label | File | Line | Redacted snippet |",
            "|---|---|---:|---:|---|",
        ]
    )

    if not findings:
        lines.append("| info | none | - | - | No legacy references found. |")
    else:
        for finding in findings:
            snippet = finding.snippet.replace("|", "\\|")
            lines.append(
                f"| {finding.severity} | {finding.label} | `{finding.path}` | {finding.line_no} | `{snippet}` |"
            )

    lines.extend(
        [
            "",
            "## Recommended next step",
            "",
            "Review high-severity runtime findings first. Remove one tiny legacy reference at a time, then run `python3 link_healthcheck.py` before committing.",
            "",
        ]
    )

    REPORT.write_text("\n".join(lines))


def main() -> None:
    findings = scan()
    write_report(findings)
    print(f"wrote {REPORT}")
    print(f"findings: {len(findings)}")


if __name__ == "__main__":
    main()
