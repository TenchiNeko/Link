#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path


def check_context_truncation_contract(strict: bool | None = None) -> None:
    """HF-01 context/truncation contract fixture.

    Default mode verifies the deterministic fixture exists and is usable.
    Strict mode is intentionally expected to fail until the ContextBundle
    metadata implementation exists.
    """

    if strict is None:
        strict = os.environ.get("LINK_HEALTHCHECK_STRICT_CONTEXT_CONTRACT") == "1"

    root = Path(__file__).resolve().parent
    fixture_dir = root / "healthcheck_fixtures" / "context_truncation"
    manifest_path = fixture_dir / "manifest.json"

    if not manifest_path.exists():
        raise AssertionError(f"context truncation manifest missing: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    missing = []
    combined = ""
    for name in manifest.get("required_files", []):
        path = fixture_dir / name
        if not path.exists():
            missing.append(name)
            continue
        combined += "\n" + path.read_text(encoding="utf-8", errors="replace")

    if missing:
        raise AssertionError(f"context truncation fixture files missing: {missing}")

    missing_sentinels = [
        sentinel
        for sentinel in manifest.get("required_sentinels", [])
        if sentinel not in combined
    ]
    if missing_sentinels:
        raise AssertionError(f"context truncation sentinels missing: {missing_sentinels}")

    if len(combined) < 50000:
        raise AssertionError("context truncation oversized fixture is too small")

    print("context truncation fixture OK")

    if not strict:
        print("context truncation strict contract skipped; set LINK_HEALTHCHECK_STRICT_CONTEXT_CONTRACT=1")
        return

    try:
        import factory.project_context as project_context  # type: ignore
    except Exception as exc:
        raise AssertionError(
            "STRICT_CONTEXT_CONTRACT_FAIL: factory.project_context could not be imported"
        ) from exc

    required_api = [
        "ContextBundle",
        "build_context_bundle",
        "load_project_context_bundle",
    ]

    available = [name for name in required_api if hasattr(project_context, name)]

    if "ContextBundle" not in available or not (
        "build_context_bundle" in available or "load_project_context_bundle" in available
    ):
        raise AssertionError(
            "STRICT_CONTEXT_CONTRACT_FAIL: ContextBundle metadata API is not implemented yet. "
            "Expected ContextBundle plus build_context_bundle() or load_project_context_bundle()."
        )

    print("context truncation strict contract API detected")


def check_context_manifest_integrity_contract() -> None:
    """LU01: validate context manifest schema, status transitions, and final-gate check."""
    from factory.project_context import build_context_manifest
    from factory.output_quality import context_manifest_quality_findings
    from factory_final_gate_audit import check_context_integrity
    from modern_context_budget import get_context_budget_summary

    budget = get_context_budget_summary(content="abcd" * 250)
    assert budget["total_chars"] == 1000
    assert budget["total_tokens_est"] > 0

    clean = build_context_manifest(
        files_included=[{
            "path": "factory/context/example.md",
            "size_bytes": 100,
            "truncated": False,
            "tail_sentinel": "OK",
            "required": True,
        }],
        files_omitted=[],
        truncation_events=[],
        context_budget=budget,
    )
    assert clean["manifest_version"] == "1.0"
    assert clean["integrity_status"] == "PASS"
    assert clean["blocking_flags"] == []
    assert check_context_integrity(clean)["diagnosis"] == "PASS"
    assert context_manifest_quality_findings(clean)["status"] == "PASS"

    warning = build_context_manifest(
        files_included=[{
            "path": "runs/old_qa_commentary.md",
            "size_bytes": 100,
            "truncated": True,
            "tail_sentinel": "OK",
            "required": False,
        }],
        files_omitted=[],
        truncation_events=[{
            "file": "runs/old_qa_commentary.md",
            "type": "soft_clip",
            "missing_bytes": 200,
            "is_deliverable": False,
        }],
        context_budget=budget,
    )
    assert warning["integrity_status"] == "WARN"
    assert warning["blocking_flags"] == []
    assert check_context_integrity(warning)["diagnosis"] == "WARN"

    fail_deliverable = build_context_manifest(
        files_included=[{
            "path": "runs/02-production_worker.md",
            "size_bytes": 500,
            "truncated": True,
            "tail_sentinel": "OK",
            "required": True,
        }],
        files_omitted=[],
        truncation_events=[{
            "file": "runs/02-production_worker.md",
            "type": "hard_clip",
            "missing_bytes": 500,
            "is_deliverable": True,
        }],
        context_budget=budget,
    )
    assert fail_deliverable["integrity_status"] == "FAIL"
    assert any("required_file_truncated" in f for f in fail_deliverable["blocking_flags"])
    assert check_context_integrity(fail_deliverable)["diagnosis"] == "FAIL"

    fail_sentinel = build_context_manifest(
        files_included=[{
            "path": "runs/02-production_worker.md",
            "size_bytes": 500,
            "truncated": False,
            "tail_sentinel": "TRUNCATED",
            "required": True,
        }],
        files_omitted=[],
        truncation_events=[],
        context_budget=budget,
    )
    assert fail_sentinel["integrity_status"] == "FAIL"
    assert any("sentinel_truncated" in f for f in fail_sentinel["blocking_flags"])

    # Determinism: identical input must produce identical output.
    clean_2 = build_context_manifest(
        files_included=[{
            "path": "factory/context/example.md",
            "size_bytes": 100,
            "truncated": False,
            "tail_sentinel": "OK",
            "required": True,
        }],
        files_omitted=[],
        truncation_events=[],
        context_budget=budget,
    )
    assert clean == clean_2

    print("context manifest integrity OK")

