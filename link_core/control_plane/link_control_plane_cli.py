"""Top-level CLI wrapper for Link control-plane workflows.

This CLI provides stable command entrypoints over the control-plane artifact
modules. It does not execute patches or verification commands.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from link_control_plane_run_index import (
    build_run_index_from_trace_paths,
    discover_trace_manifest_paths,
    write_run_index,
)
from link_control_plane_run_report import write_run_report


def build_report(
    trace_root: str | Path,
    report_path: str | Path,
    *,
    index_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    trace_paths = discover_trace_manifest_paths(trace_root)
    index = build_run_index_from_trace_paths(trace_paths, generated_at=generated_at)
    written_report = write_run_report(index, report_path)

    written_index: Path | None = None
    if index_path is not None:
        written_index = write_run_index(index, index_path)

    return {
        "trace_count": len(trace_paths),
        "report_path": str(written_report),
        "index_path": str(written_index) if written_index is not None else None,
    }


def build_status(trace_root: str | Path, *, generated_at: str | None = None) -> dict[str, Any]:
    trace_paths = discover_trace_manifest_paths(trace_root)
    index = build_run_index_from_trace_paths(trace_paths, generated_at=generated_at)
    return {
        "trace_root": str(trace_root),
        "trace_count": len(trace_paths),
        "total_runs": index["total_runs"],
        "status_counts": index["status_counts"],
        "chain_ok_count": index["chain_ok_count"],
        "chain_broken_count": index["chain_broken_count"],
    }


def render_status_lines(status: dict[str, Any]) -> list[str]:
    lines = [
        f"control plane trace root: {status['trace_root']}",
        f"control plane traces discovered: {status['trace_count']}",
        f"control plane runs indexed: {status['total_runs']}",
        f"control plane chain ok: {status['chain_ok_count']}",
        f"control plane chain broken: {status['chain_broken_count']}",
    ]

    status_counts = status.get("status_counts", {})
    if status_counts:
        for name, count in sorted(status_counts.items()):
            lines.append(f"control plane status {name}: {count}")
    else:
        lines.append("control plane statuses: none")

    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Link control-plane CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser(
        "report",
        help="Build a Markdown report from control-plane trace manifests.",
    )
    report.add_argument("--trace-root", required=True)
    report.add_argument("--report-path", required=True)
    report.add_argument("--index-path")
    report.add_argument("--generated-at")

    status = subparsers.add_parser(
        "status",
        help="Print a read-only status summary from control-plane trace manifests.",
    )
    status.add_argument("--trace-root", required=True)
    status.add_argument("--generated-at")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        result = build_report(
            args.trace_root,
            args.report_path,
            index_path=args.index_path,
            generated_at=args.generated_at,
        )
        print(f"control plane report written: {result['report_path']}")
        if result["index_path"]:
            print(f"control plane index written: {result['index_path']}")
        print(f"control plane traces discovered: {result['trace_count']}")
        return 0

    if args.command == "status":
        status = build_status(args.trace_root, generated_at=args.generated_at)
        for line in render_status_lines(status):
            print(line)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
