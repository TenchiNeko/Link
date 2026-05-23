#!/usr/bin/env python3
from __future__ import annotations

from typing import Iterable


HARD_BLOCKING_WORDS = (
    "must fix",
    "fail",
    "failed",
    "revise",
    "reject",
    "rejected",
    "not commit-ready",
)

BLOCKING_WORDS = (
    "blocking",
    "blocker",
)

NEGATED_BLOCKING_PHRASES = (
    "no blocking",
    "no blockers",
    "without blocking",
    "not blocking",
    "zero blocking",
)


def normalize_verdict(verdict: str) -> str:
    text = (verdict or "").strip().upper()
    if text in {"APPROVE", "APPROVED", "PASS"}:
        return "APPROVE"
    if text in {"REVISE", "FAIL", "FAILED", "REJECT", "REJECTED"}:
        return "REVISE"
    return "UNKNOWN"


def detect_blocking_findings(text: str) -> list[str]:
    findings = []

    for line in (text or "").splitlines():
        clean = line.strip()
        lower = clean.lower()

        if not clean:
            continue

        if any(word in lower for word in HARD_BLOCKING_WORDS):
            findings.append(clean)
            continue

        has_blocking_word = any(word in lower for word in BLOCKING_WORDS)
        has_negation = any(phrase in lower for phrase in NEGATED_BLOCKING_PHRASES)

        if has_blocking_word and not has_negation:
            findings.append(clean)

    return findings


def route_qa_result(verdict: str, qa_text: str = "", changed_files: Iterable[str] = ()) -> dict:
    normalized = normalize_verdict(verdict)
    blocking = detect_blocking_findings(qa_text)
    files = sorted(str(item) for item in changed_files)

    if normalized == "APPROVE" and not blocking:
        route = "approval_ready"
        action = "handoff_to_senior_review"
        allowed_to_commit = True
    elif normalized in {"REVISE", "UNKNOWN"} or blocking:
        route = "repair_required"
        action = "route_back_to_production_worker"
        allowed_to_commit = False
    else:
        route = "manual_review"
        action = "route_to_chief_of_staff"
        allowed_to_commit = False

    return {
        "contract_version": "1.0",
        "route": route,
        "action": action,
        "normalized_verdict": normalized,
        "blocking_findings": blocking,
        "changed_files": files,
        "allowed_to_commit": allowed_to_commit,
    }


def validate_qa_repair_route(result: dict) -> list[str]:
    problems = []

    if result.get("contract_version") != "1.0":
        problems.append("invalid_contract_version")

    route = result.get("route")
    if route not in {"approval_ready", "repair_required", "manual_review"}:
        problems.append(f"invalid_route::{route}")

    if result.get("blocking_findings") and result.get("allowed_to_commit"):
        problems.append("blocking_findings_cannot_commit")

    if route == "repair_required" and result.get("allowed_to_commit"):
        problems.append("repair_required_cannot_commit")

    if route == "approval_ready" and not result.get("allowed_to_commit"):
        problems.append("approval_ready_should_allow_commit")

    return problems


def synthetic_repair_case() -> dict:
    return route_qa_result(
        "REVISE",
        "BLOCKING-1: final gate integration missing. Must fix before approval.",
        ["factory_final_gate_audit.py", "link_healthcheck.py"],
    )


def synthetic_approval_case() -> dict:
    return route_qa_result(
        "APPROVE",
        "QA PASS. No blocking findings.",
        ["link_healthcheck.py"],
    )


def main() -> int:
    repair = synthetic_repair_case()
    approval = synthetic_approval_case()

    problems = []
    problems.extend(validate_qa_repair_route(repair))
    problems.extend(validate_qa_repair_route(approval))

    if repair["route"] != "repair_required":
        problems.append("repair_case_not_routed_to_repair")
    if repair["allowed_to_commit"]:
        problems.append("repair_case_allowed_commit")
    if approval["route"] != "approval_ready":
        problems.append("approval_case_not_ready")
    if not approval["allowed_to_commit"]:
        problems.append("approval_case_not_allowed")

    if problems:
        print("qa repair routing contract FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("qa repair routing contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
