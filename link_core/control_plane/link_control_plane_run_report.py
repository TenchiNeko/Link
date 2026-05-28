"""Markdown reports for Link control-plane run indexes.

This module renders dashboard-ready run indexes into human-readable Markdown.
It does not execute patches, run verification commands, or mutate source files
outside the report artifact written by the caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from link_control_plane_run_index import load_run_index, validate_run_index


REQUIRED_RUN_REPORT_SECTIONS: Final[tuple[str, ...]] = (
    "title",
    "summary",
    "status_counts",
    "traces",
)


def _escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_status_counts(status_counts: dict[str, int]) -> str:
    if not status_counts:
        return "_No statuses recorded._\n"

    lines = [
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {_escape_cell(status)} | {count} |")
    return "\n".join(lines) + "\n"


def render_trace_table(traces: list[dict[str, Any]]) -> str:
    if not traces:
        return "_No control-plane traces recorded._\n"

    lines = [
        "| Trace | Proposal | Title | Stage | Status | Chain | Created |",
        "|---|---|---|---|---|---|---|",
    ]

    for trace in traces:
        chain = "OK" if trace.get("chain_ok") else "BROKEN"
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(trace.get("trace_id", "")),
                    _escape_cell(trace.get("proposal_id", "")),
                    _escape_cell(trace.get("title", "")),
                    _escape_cell(trace.get("current_stage", "")),
                    _escape_cell(trace.get("status", "")),
                    _escape_cell(chain),
                    _escape_cell(trace.get("created_at", "")),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def render_run_report(index: dict[str, Any]) -> str:
    validate_run_index(index)

    lines = [
        "# Link Control-Plane Run Report",
        "",
        "## Summary",
        "",
        f"- Generated at: `{index['generated_at']}`",
        f"- Total runs: `{index['total_runs']}`",
        f"- Chain OK: `{index['chain_ok_count']}`",
        f"- Chain broken: `{index['chain_broken_count']}`",
        "",
        "## Status Counts",
        "",
        render_status_counts(index["status_counts"]).rstrip(),
        "",
        "## Traces",
        "",
        render_trace_table(index["traces"]).rstrip(),
        "",
    ]

    return "\n".join(lines)


def validate_run_report_markdown(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise TypeError("report markdown must be a non-empty string")

    required_markers = (
        "# Link Control-Plane Run Report",
        "## Summary",
        "## Status Counts",
        "## Traces",
    )
    for marker in required_markers:
        if marker not in text:
            raise ValueError(f"report markdown missing section: {marker}")


def write_run_report(index: dict[str, Any], path: str | Path) -> Path:
    report = render_run_report(index)
    validate_run_report_markdown(report)

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report + "\n", encoding="utf-8")
    return output_path


def load_run_report(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    validate_run_report_markdown(text)
    return text


def write_run_report_from_index_path(index_path: str | Path, report_path: str | Path) -> Path:
    index = load_run_index(index_path)
    return write_run_report(index, report_path)
