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
