"""CLI for generating Link control-plane run indexes and reports."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from link_control_plane_run_index import (
    build_run_index_from_trace_paths,
    discover_trace_manifest_paths,
    write_run_index,
)
from link_control_plane_run_report import write_run_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Link control-plane run index and Markdown report.")
    parser.add_argument("--trace-root", default=".agents/control_plane/traces")
    parser.add_argument("--output-dir", default=".agents/control_plane/reports")
    parser.add_argument("--index-name", default="control-plane-run-index.json")
    parser.add_argument("--report-name", default="control-plane-run-report.md")
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--print-paths", action="store_true")
    return parser


def build_index(trace_paths: list[Path], generated_at: str | None = None) -> dict:
    try:
        return build_run_index_from_trace_paths(trace_paths, generated_at=generated_at)
    except TypeError:
        index = build_run_index_from_trace_paths(trace_paths)
        if generated_at is not None:
            index["generated_at"] = generated_at
        return index


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    trace_root = Path(args.trace_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trace_paths = discover_trace_manifest_paths(trace_root)
    index = build_index(trace_paths, generated_at=args.generated_at)

    index_path = write_run_index(index, output_dir / args.index_name)
    report_path = write_run_report(index, output_dir / args.report_name)

    print(f"control plane traces: {len(trace_paths)}")
    print(f"control plane run index: {index_path}")
    print(f"control plane run report: {report_path}")

    if args.print_paths:
        for path in trace_paths:
            print(f"trace: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
