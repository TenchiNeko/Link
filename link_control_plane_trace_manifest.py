"""Trace manifests for complete Link control-plane runs.

This module ties proposal, approval, patch-plan, worker-handoff, verifier, and
finalizer artifacts into one auditable chain. It does not execute patches,
run verification commands, or mutate source files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final


CONTROL_PLANE_TRACE_STAGES: Final[tuple[str, ...]] = (
    "Proposal",
    "Approval",
    "PatchPlan",
    "WorkerHandoff",
    "VerifierReceipt",
    "FinalizerReceipt",
)

REQUIRED_TRACE_MANIFEST_FIELDS: Final[tuple[str, ...]] = (
    "trace_id",
    "proposal_id",
    "title",
    "stage_order",
    "current_stage",
    "status",
    "chain_ok",
    "artifacts",
    "created_at",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "trace"


def make_trace_id(proposal_id: str) -> str:
    digest = hashlib.sha256(proposal_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(proposal_id)}-trace-{digest}"


def _require_equal(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def validate_trace_manifest(manifest: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_TRACE_MANIFEST_FIELDS if field not in manifest]
    if missing:
        raise ValueError(f"trace manifest missing required fields: {missing}")

    for field in ("trace_id", "proposal_id", "title", "current_stage", "status", "created_at"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise TypeError(f"{field} must be a non-empty string")

    if manifest["stage_order"] != list(CONTROL_PLANE_TRACE_STAGES):
        raise ValueError("trace manifest stage_order is not canonical")

    if manifest["current_stage"] not in CONTROL_PLANE_TRACE_STAGES:
        raise ValueError(f"invalid current_stage: {manifest['current_stage']}")

    if not isinstance(manifest["chain_ok"], bool):
        raise TypeError("chain_ok must be a bool")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict):
        raise TypeError("artifacts must be a dict")

    for stage in CONTROL_PLANE_TRACE_STAGES:
        if stage not in artifacts:
            raise ValueError(f"missing artifact stage: {stage}")
        if not isinstance(artifacts[stage], dict):
            raise TypeError(f"artifact {stage} must be a dict")
        if not artifacts[stage].get("id"):
            raise ValueError(f"artifact {stage} missing id")

    proposal_id = manifest["proposal_id"]
    _require_equal("proposal artifact proposal_id", artifacts["Proposal"]["id"], proposal_id)
    _require_equal("patch plan proposal_id", artifacts["PatchPlan"]["proposal_id"], proposal_id)
    _require_equal("worker handoff proposal_id", artifacts["WorkerHandoff"]["proposal_id"], proposal_id)
    _require_equal("verifier receipt proposal_id", artifacts["VerifierReceipt"]["proposal_id"], proposal_id)
    _require_equal("finalizer receipt proposal_id", artifacts["FinalizerReceipt"]["proposal_id"], proposal_id)

    _require_equal(
        "worker handoff plan_id",
        artifacts["WorkerHandoff"]["plan_id"],
        artifacts["PatchPlan"]["id"],
    )
    _require_equal(
        "verifier receipt handoff_id",
        artifacts["VerifierReceipt"]["handoff_id"],
        artifacts["WorkerHandoff"]["id"],
    )
    _require_equal(
        "finalizer receipt verification_id",
        artifacts["FinalizerReceipt"]["verification_id"],
        artifacts["VerifierReceipt"]["id"],
    )


def build_trace_manifest(
    proposal: dict[str, Any],
    approval_receipt: dict[str, Any],
    patch_plan: dict[str, Any],
    worker_handoff: dict[str, Any],
    verifier_receipt: dict[str, Any],
    finalizer_receipt: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    proposal_id = proposal["proposal_id"]

    if approval_receipt.get("proposal_id") is not None:
        _require_equal("approval receipt proposal_id", approval_receipt["proposal_id"], proposal_id)

    manifest = {
        "trace_id": make_trace_id(proposal_id),
        "proposal_id": proposal_id,
        "title": proposal["title"],
        "stage_order": list(CONTROL_PLANE_TRACE_STAGES),
        "current_stage": "FinalizerReceipt",
        "status": finalizer_receipt["status"],
        "chain_ok": True,
        "artifacts": {
            "Proposal": {
                "id": proposal_id,
                "status": proposal.get("status", ""),
                "title": proposal.get("title", ""),
            },
            "Approval": {
                "id": approval_receipt.get("receipt_id", f"{proposal_id}-approval"),
                "proposal_id": approval_receipt.get("proposal_id", proposal_id),
                "status": approval_receipt.get("status", ""),
                "decision": approval_receipt.get("decision", ""),
            },
            "PatchPlan": {
                "id": patch_plan["plan_id"],
                "proposal_id": patch_plan["proposal_id"],
                "status": patch_plan["status"],
            },
            "WorkerHandoff": {
                "id": worker_handoff["handoff_id"],
                "plan_id": worker_handoff["plan_id"],
                "proposal_id": worker_handoff["proposal_id"],
                "status": worker_handoff["status"],
            },
            "VerifierReceipt": {
                "id": verifier_receipt["verification_id"],
                "handoff_id": verifier_receipt["handoff_id"],
                "plan_id": verifier_receipt["plan_id"],
                "proposal_id": verifier_receipt["proposal_id"],
                "status": verifier_receipt["status"],
            },
            "FinalizerReceipt": {
                "id": finalizer_receipt["finalization_id"],
                "verification_id": finalizer_receipt["verification_id"],
                "handoff_id": finalizer_receipt["handoff_id"],
                "plan_id": finalizer_receipt["plan_id"],
                "proposal_id": finalizer_receipt["proposal_id"],
                "status": finalizer_receipt["status"],
            },
        },
        "created_at": created_at or utc_now(),
    }
    validate_trace_manifest(manifest)
    return manifest


def trace_manifest_to_json(manifest: dict[str, Any]) -> str:
    validate_trace_manifest(manifest)
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def trace_manifest_from_json(text: str) -> dict[str, Any]:
    manifest = json.loads(text)
    validate_trace_manifest(manifest)
    return manifest


def write_trace_manifest(manifest: dict[str, Any], root: str | Path) -> Path:
    validate_trace_manifest(manifest)
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    path = root_path / f"{manifest['trace_id']}.json"
    path.write_text(trace_manifest_to_json(manifest), encoding="utf-8")
    return path


def load_trace_manifest(path: str | Path) -> dict[str, Any]:
    return trace_manifest_from_json(Path(path).read_text(encoding="utf-8"))


def list_trace_manifests(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(root_path.glob("*.json"))
