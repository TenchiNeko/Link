
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "UNKNOWN").upper()


def _commit(row: dict[str, Any]) -> str:
    return str(row.get("commit") or row.get("head") or row.get("git_head") or "").strip()


def summarize_rows(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    summary = []
    for row in rows[:limit]:
        summary.append({
            "archive": row.get("archive", ""),
            "created_at": row.get("created_at", ""),
            "status": _status(row),
            "commit": _commit(row),
            "markers": list(row.get("markers", [])),
        })
    return summary


def advise_from_rows(rows: list[dict[str, Any]], current_head: str | None = None) -> dict[str, Any]:
    rows = list(rows)
    current_head = current_head or _git(["rev-parse", "HEAD"])

    result: dict[str, Any] = {
        "advisor_version": "1.0",
        "current_head": current_head,
        "latest_archive": None,
        "latest_status": "UNKNOWN",
        "rollback_candidate": "",
        "recommendation": "NO_EVIDENCE",
        "reason": "No retained healthcheck evidence archives were found.",
        "recent_evidence": summarize_rows(rows),
        "safe_actions": [],
    }

    if not rows:
        return result

    latest = rows[0]
    latest_status = _status(latest)
    latest_commit = _commit(latest)

    latest_pass = next((row for row in rows if _status(row) == "PASS" and _commit(row)), None)
    latest_fail = next((row for row in rows if _status(row) == "FAIL"), None)

    result["latest_archive"] = latest.get("archive", "")
    result["latest_status"] = latest_status

    if latest_status == "PASS":
        result["recommendation"] = "NO_ROLLBACK_NEEDED"
        result["reason"] = "Most recent retained healthcheck evidence passed."
        result["rollback_candidate"] = latest_commit
        result["safe_actions"] = [
            "Keep current HEAD unless a newer failing run appears.",
            "Use evidence bundle export before any risky change.",
        ]
        return result

    if latest_status == "FAIL" and latest_pass:
        candidate = _commit(latest_pass)
        result["recommendation"] = "ADVISE_ROLLBACK_TO_LAST_PASS"
        result["rollback_candidate"] = candidate
        result["reason"] = "Most recent evidence failed; a prior passing healthcheck archive exists."
        result["safe_actions"] = [
            f"Inspect diff from candidate to HEAD: git diff {candidate}..HEAD",
            f"Create review branch before rollback: git checkout -b rollback-review {candidate}",
            "Do not run reset --hard or clean -fdx without explicit human approval.",
        ]
        return result

    if latest_status == "FAIL" and latest_fail:
        result["recommendation"] = "BLOCK_ROLLBACK_NO_KNOWN_GOOD"
        result["reason"] = "Most recent evidence failed, but no prior passing archive with a commit was found."
        result["safe_actions"] = [
            "Investigate the failure log first.",
            "Run python3 link_healthcheck.py after repair.",
            "Archive evidence before attempting rollback.",
        ]
        return result

    result["recommendation"] = "INVESTIGATE"
    result["reason"] = f"Most recent evidence status is {latest_status}; no automatic rollback target selected."
    result["safe_actions"] = [
        "Inspect healthcheck evidence index.",
        "Confirm a passing commit before creating any rollback branch.",
    ]
    return result


def advise_from_archive(root: str | Path | None = None) -> dict[str, Any]:
    from healthcheck_evidence_index import build_evidence_index

    index = build_evidence_index(root)
    return advise_from_rows(index.get("archives", []))


def format_advice(advice: dict[str, Any]) -> str:
    lines = [
        "Evidence-aware rollback advisor",
        f"recommendation: {advice.get('recommendation')}",
        f"reason: {advice.get('reason')}",
        f"current_head: {advice.get('current_head') or '-'}",
        f"rollback_candidate: {advice.get('rollback_candidate') or '-'}",
    ]

    actions = advice.get("safe_actions") or []
    if actions:
        lines.append("safe_actions:")
        for action in actions:
            lines.append(f"- {action}")

    recent = advice.get("recent_evidence") or []
    if recent:
        lines.append("recent_evidence:")
        for row in recent:
            lines.append(
                f"- {row.get('archive')} [{row.get('status')}] "
                f"commit={row.get('commit') or '-'}"
            )

    return "\n".join(lines)


def self_test() -> list[str]:
    problems = []

    rows_fail_then_pass = [
        {
            "archive": "20260102-fail",
            "created_at": "2026-01-02T00:00:00Z",
            "status": "FAIL",
            "commit": "bad222",
            "markers": ["FAILED"],
        },
        {
            "archive": "20260101-pass",
            "created_at": "2026-01-01T00:00:00Z",
            "status": "PASS",
            "commit": "good111",
            "markers": ["LINK HEALTHCHECK PASSED"],
        },
    ]
    advice = advise_from_rows(rows_fail_then_pass, current_head="bad222")
    if advice["recommendation"] != "ADVISE_ROLLBACK_TO_LAST_PASS":
        problems.append("failed_latest_should_advise_rollback")
    if advice["rollback_candidate"] != "good111":
        problems.append("wrong_rollback_candidate")

    rows_pass_latest = [
        {
            "archive": "20260103-pass",
            "created_at": "2026-01-03T00:00:00Z",
            "status": "PASS",
            "commit": "good333",
            "markers": ["LINK HEALTHCHECK PASSED"],
        }
    ]
    advice = advise_from_rows(rows_pass_latest, current_head="good333")
    if advice["recommendation"] != "NO_ROLLBACK_NEEDED":
        problems.append("pass_latest_should_not_rollback")

    advice = advise_from_rows([], current_head="abc")
    if advice["recommendation"] != "NO_EVIDENCE":
        problems.append("empty_evidence_should_report_no_evidence")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Advise rollback target from retained healthcheck evidence.")
    parser.add_argument("--root", default=None, help="Healthcheck evidence archive root.")
    parser.add_argument("--json", action="store_true", help="Print JSON advice.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("evidence rollback advisor FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("evidence rollback advisor OK")
        return 0

    advice = advise_from_archive(args.root)
    if args.json:
        print(json.dumps(advice, indent=2, sort_keys=True))
    else:
        print(format_advice(advice))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
