#!/usr/bin/env python3
from __future__ import annotations

"""
Link Route Intelligence.

Deterministic pre-run router for Link web requests.

Routes:
- audit_fastpath -> link_audit_fast.py
- micro_patch    -> link_micro_patch.py
- autonomous     -> link_autonomous.py

This module does not edit source files. It may call the read-only specialist
fanout, which writes normal generated artifacts under .agents/.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from link_runtime_policy import is_micro_patch_prompt, is_read_only_prompt

ROOT = Path(__file__).resolve().parent

ROUTE_RUNNERS = {
    "audit_fastpath": "link_audit_fast.py",
    "micro_patch": "link_micro_patch.py",
    "autonomous": "link_autonomous.py",
}


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(str(prompt or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def _safe_json_load(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as exc:
        return {"_load_error": str(exc)}
    return {}


def run_specialist_fanout_for_route(prompt: str, timeout: int = 25) -> dict[str, Any]:
    run_id = f"route-{_prompt_hash(prompt)}-{int(time.time())}"
    json_path = ROOT / ".agents" / "tool_results" / run_id / "specialist_fanout.json"
    cmd = [sys.executable, str(ROOT / "link_specialist_fanout.py"), "--run-id", run_id]

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        data = _safe_json_load(json_path)
        return {
            "ok": proc.returncode == 0 and json_path.exists(),
            "run_id": run_id,
            "exit_code": proc.returncode,
            "json_path": str(json_path) if json_path.exists() else None,
            "summary_path": data.get("summary_path") if isinstance(data, dict) else None,
            "duration_sec": round(time.time() - started, 3),
            "stdout_preview": (proc.stdout or "")[-1000:],
            "stderr_preview": (proc.stderr or "")[-1000:],
            "data": data,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "run_id": run_id,
            "exit_code": None,
            "json_path": None,
            "summary_path": None,
            "duration_sec": round(time.time() - started, 3),
            "error": f"fanout timeout after {timeout}s",
            "stdout_preview": (exc.stdout or "")[-1000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
            "data": {},
        }
    except Exception as exc:
        return {
            "ok": False,
            "run_id": run_id,
            "exit_code": None,
            "json_path": None,
            "summary_path": None,
            "duration_sec": round(time.time() - started, 3),
            "error": str(exc),
            "data": {},
        }


def _latest_failure_hint(fanout: dict[str, Any]) -> str | None:
    data = fanout.get("data") if isinstance(fanout, dict) else {}
    if not isinstance(data, dict):
        return None

    text = json.dumps(data.get("latest_failures"), sort_keys=True, default=str).lower()
    for marker in ["stuck_loop", "verification_failed", "blocked", "failed"]:
        if marker in text:
            return marker
    return None


def _repo_dirty_hint(fanout: dict[str, Any]) -> bool:
    data = fanout.get("data") if isinstance(fanout, dict) else {}
    if not isinstance(data, dict):
        return False

    text = json.dumps(data.get("repo_state"), sort_keys=True, default=str).lower()

    clean_markers = [
        '"dirty": false',
        '"is_dirty": false',
        '"clean": true',
        "clean repo",
        "git status clean",
    ]
    dirty_markers = [
        '"dirty": true',
        '"is_dirty": true',
        '"clean": false',
        "dirty files",
        "modified:",
        "untracked",
        "git status dirty",
    ]

    if any(marker in text for marker in clean_markers):
        return False
    return any(marker in text for marker in dirty_markers)


def _looks_like_retry_or_diagnosis(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(
        marker in lower
        for marker in [
            "retry",
            "rerun",
            "same prompt",
            "why did it fail",
            "diagnose",
            "inspect failure",
            "what happened",
            "latest failure",
            "handoff",
            "doctor",
            "healthcheck",
        ]
    )


def decide_route(
    prompt: str,
    audit_only: bool = False,
    run_fanout: bool = True,
    fanout_timeout: int = 25,
) -> dict[str, Any]:
    raw_prompt = str(prompt or "")
    reasons: list[str] = []

    if run_fanout:
        fanout = run_specialist_fanout_for_route(raw_prompt, timeout=fanout_timeout)
        reasons.append("specialist_fanout_ok" if fanout.get("ok") else "specialist_fanout_unavailable")
    else:
        fanout = {"ok": False, "skipped": True, "data": {}}
        reasons.append("specialist_fanout_skipped")

    read_only = bool(audit_only) or is_read_only_prompt(raw_prompt)
    micro_patch = (not read_only) and is_micro_patch_prompt(raw_prompt)

    if audit_only:
        route = "audit_fastpath"
        confidence = "high"
        reasons.append("ui_audit_only_true")
    elif read_only:
        route = "audit_fastpath"
        confidence = "high"
        reasons.append("prompt_read_only_detected")
    elif micro_patch:
        route = "micro_patch"
        confidence = "high"
        reasons.append("micro_patch_prompt_detected")
    else:
        route = "autonomous"
        confidence = "medium"
        reasons.append("default_full_autonomous")

    latest_failure = _latest_failure_hint(fanout)
    repo_dirty = _repo_dirty_hint(fanout)

    if repo_dirty and route == "autonomous":
        route = "audit_fastpath"
        confidence = "high"
        reasons.append("repo_dirty_guard_routed_to_audit")

    if latest_failure == "stuck_loop" and route == "autonomous" and _looks_like_retry_or_diagnosis(raw_prompt):
        route = "audit_fastpath"
        confidence = "high"
        reasons.append("latest_stuck_loop_diagnosis_guard")

    return {
        "route": route,
        "runner": ROUTE_RUNNERS[route],
        "confidence": confidence,
        "reasons": reasons,
        "audit_only": bool(audit_only),
        "read_only_detected": bool(read_only),
        "micro_patch_detected": bool(micro_patch),
        "latest_failure_hint": latest_failure,
        "repo_dirty_hint": bool(repo_dirty),
        "prompt_hash": _prompt_hash(raw_prompt),
        "fanout": {
            "ok": bool(fanout.get("ok")),
            "run_id": fanout.get("run_id"),
            "json_path": fanout.get("json_path"),
            "summary_path": fanout.get("summary_path"),
            "duration_sec": fanout.get("duration_sec"),
            "error": fanout.get("error"),
        },
    }


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return args.prompt or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Link route intelligence")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--no-fanout", action="store_true")
    parser.add_argument("--fanout-timeout", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    decision = decide_route(
        _read_prompt(args),
        audit_only=args.audit_only,
        run_fanout=not args.no_fanout,
        fanout_timeout=args.fanout_timeout,
    )

    if args.json:
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(f"route: {decision['route']}")
        print(f"runner: {decision['runner']}")
        print(f"confidence: {decision['confidence']}")
        print("reasons:")
        for reason in decision["reasons"]:
            print(f"- {reason}")
        fanout = decision.get("fanout") or {}
        if fanout.get("json_path"):
            print(f"fanout_json: {fanout['json_path']}")
        if fanout.get("summary_path"):
            print(f"fanout_summary: {fanout['summary_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
