"""Run indexes for Link control-plane trace manifests.

This module summarizes control-plane trace manifests into one dashboard-ready
index. It does not execute patches, run verification, or mutate source files
outside the index artifact written by the caller.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from link_control_plane_trace_manifest import load_trace_manifest, validate_trace_manifest


REQUIRED_RUN_INDEX_FIELDS: Final[tuple[str, ...]] = (
    "generated_at",
    "total_runs",
    "status_counts",
    "chain_ok_count",
    "chain_broken_count",
    "traces",
)

REQUIRED_TRACE_INDEX_FIELDS: Final[tuple[str, ...]] = (
    "trace_id",
    "proposal_id",
    "title",
    "current_stage",
    "status",
    "chain_ok",
    "created_at",
    "artifact_ids",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_trace_index_entry(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_trace_manifest(manifest)
    artifacts = manifest["artifacts"]

    entry = {
        "trace_id": manifest["trace_id"],
        "proposal_id": manifest["proposal_id"],
        "title": manifest["title"],
        "current_stage": manifest["current_stage"],
        "status": manifest["status"],
        "chain_ok": manifest["chain_ok"],
        "created_at": manifest["created_at"],
        "artifact_ids": {
            stage: artifact["id"]
            for stage, artifact in artifacts.items()
        },
    }
    validate_trace_index_entry(entry)
    return entry


def validate_trace_index_entry(entry: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_TRACE_INDEX_FIELDS if field not in entry]
    if missing:
        raise ValueError(f"trace index entry missing required fields: {missing}")

    for field in ("trace_id", "proposal_id", "title", "current_stage", "status", "created_at"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise TypeError(f"{field} must be a non-empty string")

    if not isinstance(entry["chain_ok"], bool):
        raise TypeError("chain_ok must be a bool")

    if not isinstance(entry["artifact_ids"], dict) or not entry["artifact_ids"]:
        raise TypeError("artifact_ids must be a non-empty dict")


def build_run_index(
    manifests: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    entries = [build_trace_index_entry(manifest) for manifest in manifests]
    entries.sort(key=lambda item: (item["created_at"], item["trace_id"]), reverse=True)

    status_counts: dict[str, int] = {}
    for entry in entries:
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

    chain_ok_count = sum(1 for entry in entries if entry["chain_ok"])
    index = {
        "generated_at": generated_at or utc_now(),
        "total_runs": len(entries),
        "status_counts": dict(sorted(status_counts.items())),
        "chain_ok_count": chain_ok_count,
        "chain_broken_count": len(entries) - chain_ok_count,
        "traces": entries,
    }
    validate_run_index(index)
    return index


def validate_run_index(index: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_RUN_INDEX_FIELDS if field not in index]
    if missing:
        raise ValueError(f"run index missing required fields: {missing}")

    if not isinstance(index["generated_at"], str) or not index["generated_at"].strip():
        raise TypeError("generated_at must be a non-empty string")

    if not isinstance(index["total_runs"], int) or index["total_runs"] < 0:
        raise TypeError("total_runs must be a non-negative int")

    if not isinstance(index["status_counts"], dict):
        raise TypeError("status_counts must be a dict")

    for field in ("chain_ok_count", "chain_broken_count"):
        if not isinstance(index[field], int) or index[field] < 0:
            raise TypeError(f"{field} must be a non-negative int")

    traces = index["traces"]
    if not isinstance(traces, list):
        raise TypeError("traces must be a list")

    if index["total_runs"] != len(traces):
        raise ValueError("total_runs does not match traces length")

    if index["chain_ok_count"] + index["chain_broken_count"] != len(traces):
        raise ValueError("chain counts do not match traces length")

    for entry in traces:
        validate_trace_index_entry(entry)


def run_index_to_json(index: dict[str, Any]) -> str:
    validate_run_index(index)
    return json.dumps(index, indent=2, sort_keys=True) + "\n"


def run_index_from_json(text: str) -> dict[str, Any]:
    index = json.loads(text)
    validate_run_index(index)
    return index


def write_run_index(index: dict[str, Any], path: str | Path) -> Path:
    validate_run_index(index)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(run_index_to_json(index), encoding="utf-8")
    return output_path


def load_run_index(path: str | Path) -> dict[str, Any]:
    return run_index_from_json(Path(path).read_text(encoding="utf-8"))


def build_run_index_from_trace_paths(
    trace_paths: list[str | Path],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    manifests = [load_trace_manifest(path) for path in trace_paths]
    return build_run_index(manifests, generated_at=generated_at)


def discover_trace_manifest_paths(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(path for path in root_path.rglob("*.json") if path.is_file())
