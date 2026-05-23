#!/usr/bin/env python3
from __future__ import annotations

UPGRADES = [
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "context truncation fixture OK"
        ],
        "id": "LU01",
        "status": "implemented",
        "title": "Context manifest and truncation hardening"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "capability gate OK"
        ],
        "id": "LU02",
        "status": "implemented",
        "title": "Unified capability safety gate"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "execution receipts OK"
        ],
        "id": "LU03",
        "status": "implemented",
        "title": "Execution receipts audit trail"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "execution snapshots OK"
        ],
        "id": "LU04",
        "status": "implemented",
        "title": "Rollback execution snapshots"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "upgrade registry OK"
        ],
        "id": "LU05",
        "status": "implemented",
        "title": "Upgrade registry"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "planner acceptance contract OK"
        ],
        "id": "LU06",
        "status": "implemented",
        "title": "Planner-to-implementation acceptance contract"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "upgrade status badges OK"
        ],
        "id": "LU07",
        "status": "implemented",
        "title": "Implementation status dashboard badges"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "upgrade diff receipt cross-check OK"
        ],
        "id": "LU08",
        "status": "implemented",
        "title": "Upgrade diff/receipt cross-check"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "qa repair routing contract OK"
        ],
        "id": "LU09",
        "status": "implemented",
        "title": "Automated QA repair routing contract"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "upgrade evidence bundle OK"
        ],
        "id": "LU10",
        "status": "implemented",
        "title": "Upgrade evidence bundle exporter"
    },
    {
        "commit_subject": "",
        "healthcheck_markers": [
            "healthcheck evidence archive OK"
        ],
        "id": "LU11",
        "status": "implemented",
        "title": "Healthcheck evidence archive retention"
    },
    {
        "commit_subject": "feat: add healthcheck evidence index and search LU12",
        "healthcheck_markers": [
            "healthcheck evidence index OK"
        ],
        "id": "LU12",
        "status": "implemented",
        "title": "Healthcheck evidence index and search"
    }
]

NEXT_UPGRADE = {
    "id": "LU13",
    "status": "planned",
    "title": "Evidence-aware rollback advisor"
}


def implemented_upgrade_ids() -> list[str]:
    return [item["id"] if isinstance(item, dict) else item[0] for item in UPGRADES]


def validate_registry() -> list[str]:
    problems = []
    seen = set()

    for item in UPGRADES:
        if isinstance(item, dict):
            uid = item.get("id", "")
            title = item.get("title", "")
            markers = item.get("healthcheck_markers", [])
        else:
            uid, title, marker = item
            markers = [marker]

        if uid in seen:
            problems.append(f"duplicate upgrade id: {uid}")
        seen.add(uid)

        if not uid:
            problems.append("upgrade missing id")
        if not title:
            problems.append(f"{uid} missing title")
        if not markers:
            problems.append(f"{uid} missing healthcheck marker")

    if not NEXT_UPGRADE.get("id"):
        problems.append("missing next upgrade id")
    if not NEXT_UPGRADE.get("title"):
        problems.append("missing next upgrade title")

    return problems


def main() -> int:
    problems = validate_registry()
    if problems:
        print("upgrade registry FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("upgrade registry OK")
    print("implemented: " + ", ".join(implemented_upgrade_ids()))
    print(f"next: {NEXT_UPGRADE['id']} - {NEXT_UPGRADE['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
