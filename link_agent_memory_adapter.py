#!/usr/bin/env python3
"""Outcome memory + prompt injection adapter for Link agents.

Stores advisory per-role memory under .link/agent_memory and queue receipts under
.link/agent_queue/receipts. This adapter is intentionally append-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from link_agent_identity import (
    DEFAULT_PROJECT,
    ensure_memory_tree,
    ensure_role_identity,
    role_dir,
    safe_role_id,
)


SCHEMA_VERSION = "LU292-agent-memory-v1"
QUEUE_ROOT = Path(".link/agent_queue")
RECEIPTS_DIR = QUEUE_ROOT / "receipts"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str, fallback: str = "event") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw)
    raw = raw.strip("-._")
    return (raw or fallback)[:120]


def outcome_bucket(outcome: str) -> str:
    normalized = safe_slug(outcome, "neutral")
    if normalized in {"pass", "passed", "positive", "approved", "success", "qa-pass"}:
        return "positive"
    if normalized in {"fail", "failed", "negative", "rejected", "blocked", "error", "qa-fail"}:
        return "negative"
    return "neutral"


def event_hash(event: dict[str, Any]) -> str:
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def append_event(
    role_id: str,
    event_type: str,
    outcome: str,
    details: str,
    *,
    task_id: str | None = None,
    evidence_path: str | None = None,
    project: str = DEFAULT_PROJECT,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = ensure_role_identity(role_id, project)
    tree = ensure_memory_tree(role_id, project)
    rid = safe_role_id(role_id)

    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "project": project,
        "role_id": rid,
        "agent_id": identity["agent_id"],
        "event_type": safe_slug(event_type),
        "outcome": safe_slug(outcome),
        "details": str(details or "").strip(),
        "task_id": task_id,
        "evidence_path": evidence_path,
    }
    if extra:
        event["extra"] = extra
    event["receipt_id"] = event_hash(event)

    base = role_dir(rid)
    bucket = outcome_bucket(event["outcome"])
    event_path = base / bucket / f'{event["timestamp"].replace(":", "").replace("+", "Z")}-{event["receipt_id"]}.json'
    event_path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n")

    with Path(tree["events"]).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")

    write_queue_receipt(event, event_path)
    return event


def write_queue_receipt(event: dict[str, Any], event_path: Path) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    task = safe_slug(str(event.get("task_id") or "manual"))
    role = safe_slug(str(event.get("role_id") or "role"))
    etype = safe_slug(str(event.get("event_type") or "event"))
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    receipt_path = RECEIPTS_DIR / f"{ts}-{task}-{role}-{etype}-{event['receipt_id']}.json"

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "role_id": event.get("role_id"),
        "agent_id": event.get("agent_id"),
        "task_id": event.get("task_id"),
        "event_type": event.get("event_type"),
        "outcome": event.get("outcome"),
        "status": "recorded",
        "evidence_path": str(event_path),
        "receipt_id": event.get("receipt_id"),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt_path


def record_qa_outcome(role_id: str, task_id: str, verdict: str, details: str, evidence_path: str | None = None) -> dict[str, Any]:
    return append_event(role_id, "qa_outcome", verdict, details, task_id=task_id, evidence_path=evidence_path)


def record_human_verdict(role_id: str, task_id: str, verdict: str, details: str, evidence_path: str | None = None) -> dict[str, Any]:
    return append_event(role_id, "human_verdict", verdict, details, task_id=task_id, evidence_path=evidence_path)


def record_blocked_command(role_id: str, task_id: str, command: str, reason: str, evidence_path: str | None = None) -> dict[str, Any]:
    return append_event(
        role_id,
        "blocked_command",
        "blocked",
        reason,
        task_id=task_id,
        evidence_path=evidence_path,
        extra={"command": command},
    )


def read_events(role_id: str, limit: int = 50) -> list[dict[str, Any]]:
    events_path = role_dir(role_id) / "events.jsonl"
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events[-limit:]


def inject_memory_prompt(role_id: str, limit: int = 5) -> str:
    identity = ensure_role_identity(role_id)
    events = read_events(role_id, limit=50)
    positives = [e for e in events if outcome_bucket(str(e.get("outcome"))) == "positive"][-limit:]
    negatives = [e for e in events if outcome_bucket(str(e.get("outcome"))) == "negative"][-limit:]

    lines = [
        f"Agent memory advisory for role_id={identity['role_id']} agent_id={identity['agent_id']}.",
        "Memory is advisory only; verify live repo state before acting.",
    ]
    if positives:
        lines.append("Positive patterns:")
        lines.extend(f"- {e.get('event_type')}: {e.get('details')}"[:220] for e in positives)
    if negatives:
        lines.append("Negative/blocked patterns:")
        lines.extend(f"- {e.get('event_type')}: {e.get('details')}"[:220] for e in negatives)
    if len(lines) == 2:
        lines.append("- No prior role memory events recorded.")
    return "\n".join(lines)


def healthcheck(role_ids: list[str] | None = None) -> dict[str, Any]:
    role_ids = role_ids or ["chief_of_staff", "research_worker", "web_researcher", "production_lead", "production_worker", "qa_worker"]
    checks = []
    ok = True
    for role_id in role_ids:
        identity = ensure_role_identity(role_id)
        tree = ensure_memory_tree(role_id)
        missing = [name for name, path in tree.items() if not Path(path).exists()]
        if missing:
            ok = False
        checks.append({"role_id": safe_role_id(role_id), "agent_id": identity["agent_id"], "missing": missing})
    return {"schema_version": SCHEMA_VERSION, "ok": ok, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Link agent memory adapter")
    parser.add_argument("--role-id", default="qa_worker")
    parser.add_argument("--task-id", default="manual")
    parser.add_argument("--details", default="")
    parser.add_argument("--evidence-path", default=None)
    parser.add_argument("--record-qa", choices=["PASS", "FAIL", "pass", "fail"])
    parser.add_argument("--record-human", choices=["approved", "rejected", "APPROVED", "REJECTED"])
    parser.add_argument("--blocked-command")
    parser.add_argument("--blocked-reason", default="missing_real_consumer_command")
    parser.add_argument("--inject", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    result: Any
    if args.healthcheck:
        result = healthcheck()
    elif args.inject:
        result = inject_memory_prompt(args.role_id)
    elif args.record_qa:
        result = record_qa_outcome(args.role_id, args.task_id, args.record_qa, args.details, args.evidence_path)
    elif args.record_human:
        result = record_human_verdict(args.role_id, args.task_id, args.record_human, args.details, args.evidence_path)
    elif args.blocked_command:
        result = record_blocked_command(args.role_id, args.task_id, args.blocked_command, args.blocked_reason, args.evidence_path)
    else:
        ensure_role_identity(args.role_id)
        result = healthcheck([args.role_id])

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if isinstance(result, str):
            print(result)
        else:
            print("# Link Agent Memory Adapter")
            print()
            print(f"- ok: `{result.get('ok', True)}`" if isinstance(result, dict) else "- ok: `true`")
            print()
            print("```json")
            print(json.dumps(result, indent=2, sort_keys=True))
            print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
