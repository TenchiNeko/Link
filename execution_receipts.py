#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import re
import uuid


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT_DIR = ROOT / ".agents" / "receipts"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_slug(text: str, limit: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(text).strip()).strip("-")
    return (slug or "receipt")[:limit]


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(data: Any) -> str:
    return hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()


def normalize_decision(decision: Any) -> dict[str, Any]:
    if decision is None:
        return {"kind": "unknown", "target": "", "decision": "unknown", "reason": "no decision supplied", "source": "unknown", "metadata": {}}

    if is_dataclass(decision):
        raw = asdict(decision)
    elif isinstance(decision, Mapping):
        raw = dict(decision)
    else:
        raw = {
            "kind": getattr(decision, "kind", "unknown"),
            "target": getattr(decision, "target", ""),
            "decision": getattr(decision, "decision", "unknown"),
            "reason": getattr(decision, "reason", ""),
            "source": getattr(decision, "source", "unknown"),
            "metadata": getattr(decision, "metadata", {}) or {},
        }

    return {
        "kind": raw.get("kind", "unknown"),
        "target": raw.get("target", ""),
        "decision": raw.get("decision", "unknown"),
        "reason": raw.get("reason", ""),
        "source": raw.get("source", "unknown"),
        "metadata": raw.get("metadata", {}) or {},
    }


def build_execution_receipt(
    *,
    action: str,
    target: str | list[str],
    gate_decision: Any,
    outcome: str,
    actor: str = "link",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = {
        "receipt_version": "1.0",
        "receipt_id": str(uuid.uuid4()),
        "created_at": _utc_now(),
        "actor": actor,
        "action": str(action),
        "target": target,
        "target_sha256": _sha256(target),
        "gate": normalize_decision(gate_decision),
        "outcome": str(outcome),
        "details": dict(details or {}),
    }
    receipt["receipt_sha256"] = _sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    return receipt


def write_execution_receipt(
    *,
    action: str,
    target: str | list[str],
    gate_decision: Any,
    outcome: str,
    actor: str = "link",
    details: Mapping[str, Any] | None = None,
    receipt_dir: str | Path | None = None,
) -> Path:
    receipt = build_execution_receipt(
        action=action,
        target=target,
        gate_decision=gate_decision,
        outcome=outcome,
        actor=actor,
        details=details,
    )

    base = Path(receipt_dir) if receipt_dir else DEFAULT_RECEIPT_DIR
    base.mkdir(parents=True, exist_ok=True)

    slug = _safe_slug(f"{action}-{receipt['gate'].get('decision')}")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slug}-{receipt['receipt_id'][:8]}.json"
    path = base / name
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def verify_execution_receipt(path: str | Path) -> bool:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = data.get("receipt_sha256")
    actual = _sha256({k: v for k, v in data.items() if k != "receipt_sha256"})
    return bool(expected and expected == actual)


def latest_receipts(limit: int = 10, receipt_dir: str | Path | None = None) -> list[Path]:
    base = Path(receipt_dir) if receipt_dir else DEFAULT_RECEIPT_DIR
    if not base.exists():
        return []
    return sorted(base.glob("*.json"), reverse=True)[:limit]
