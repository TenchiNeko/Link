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
        "report_path": written_report,
        "index_path": written_index,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Link control-plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser(
        "report",
        help="Build a control-plane run index and Markdown report from trace manifests.",
    )
    report.add_argument("--trace-root", required=True, help="Directory containing trace manifest JSON files.")
    report.add_argument("--out", required=True, help="Markdown report output path.")
    report.add_argument("--index-out", help="Optional JSON run-index output path.")
    report.add_argument("--generated-at", help="Optional deterministic generated_at timestamp.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        result = build_report(
            args.trace_root,
            args.out,
            index_path=args.index_out,
            generated_at=args.generated_at,
        )
        print(f"control plane report written: {result['report_path']}")
        if result["index_path"] is not None:
            print(f"control plane index written: {result['index_path']}")
        print(f"control plane traces indexed: {result['trace_count']}")
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
