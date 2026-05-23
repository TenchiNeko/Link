
#!/usr/bin/env python3
from __future__ import annotations

UPGRADES = [
    {
        "id": "LU01",
        "title": "Context manifest and truncation hardening",
        "commit_subject": "feat: add context manifest and truncation hardening LU01",
        "healthcheck_markers": ["context truncation fixture OK", "context manifest integrity OK"],
        "status": "implemented",
    },
    {
        "id": "LU02",
        "title": "Unified capability safety gate",
        "commit_subject": "feat: add unified capability safety gate LU02",
        "healthcheck_markers": ["capability gate OK"],
        "status": "implemented",
    },
    {
        "id": "LU03",
        "title": "Execution receipts audit trail",
        "commit_subject": "feat: add execution receipts audit trail LU03",
        "healthcheck_markers": ["execution receipts OK"],
        "status": "implemented",
    },
    {
        "id": "LU04",
        "title": "Rollback execution snapshots",
        "commit_subject": "feat: add rollback execution snapshots LU04",
        "healthcheck_markers": ["execution snapshots OK", "web admin snapshot wiring OK"],
        "status": "implemented",
    },
    {
        "id": "LU05",
        "title": "Upgrade registry",
        "commit_subject": "feat: add upgrade registry LU05",
        "healthcheck_markers": ["upgrade registry OK"],
        "status": "implemented",
    },
    {
        "id": "LU06",
        "title": "Planner-to-implementation acceptance contract",
        "commit_subject": "feat: add planner acceptance contract LU06",
        "healthcheck_markers": ["planner acceptance contract OK"],
        "status": "implemented",
    },
    {
        "id": "LU07",
        "title": "Implementation status dashboard badges",
        "commit_subject": "feat: add upgrade status dashboard badges LU07",
        "healthcheck_markers": ["upgrade status badges OK"],
        "status": "implemented",
    },
    {
        "id": "LU08",
        "title": "Upgrade diff/receipt cross-check",
        "commit_subject": "feat: add upgrade diff receipt cross-check LU08",
        "healthcheck_markers": ["upgrade diff receipt cross-check OK"],
        "status": "implemented",
    },
    {
        "id": "LU09",
        "title": "Automated QA repair routing contract",
        "commit_subject": "feat: add QA repair routing contract LU09",
        "healthcheck_markers": ["qa repair routing contract OK"],
        "status": "implemented",
    },
    {
        "id": "LU10",
        "title": "Upgrade evidence bundle exporter",
        "commit_subject": "feat: add upgrade evidence bundle exporter LU10",
        "healthcheck_markers": ["upgrade evidence bundle OK"],
        "status": "implemented",
    },
]

NEXT_UPGRADE = {
    "id": "LU11",
    "title": "Healthcheck evidence archive retention",
    "status": "planned",
}


def implemented_upgrade_ids() -> list[str]:
    return [str(item["id"]) for item in UPGRADES]


def validate_registry() -> list[str]:
    problems = []
    seen = set()

    for item in UPGRADES:
        uid = str(item.get("id", ""))
        title = str(item.get("title", ""))
        markers = item.get("healthcheck_markers", [])
        subject = str(item.get("commit_subject", ""))

        if uid in seen:
            problems.append(f"duplicate upgrade id: {uid}")
        seen.add(uid)

        if not uid:
            problems.append("upgrade missing id")
        if not title:
            problems.append(f"{uid} missing title")
        if not markers:
            problems.append(f"{uid} missing healthcheck marker")
        if not subject:
            problems.append(f"{uid} missing commit subject")

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
