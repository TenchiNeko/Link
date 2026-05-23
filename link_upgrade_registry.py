#!/usr/bin/env python3
from __future__ import annotations

UPGRADES = [
    ('LU01', 'Context manifest and truncation hardening', 'context truncation fixture OK'),
    ('LU02', 'Unified capability safety gate', 'capability gate OK'),
    ('LU03', 'Execution receipts audit trail', 'execution receipts OK'),
    ('LU04', 'Rollback execution snapshots', 'execution snapshots OK'),
    ('LU05', 'Upgrade registry', 'upgrade registry OK'),
    ('LU06', 'Planner-to-implementation acceptance contract', 'planner acceptance contract OK'),
    ('LU07', 'Implementation status dashboard badges', 'upgrade status badges OK'),
    ('LU08', 'Upgrade diff/receipt cross-check', 'upgrade diff receipt cross-check OK'),
    ('LU09', 'Automated QA repair routing contract', 'qa repair routing contract OK'),
    ('LU10', 'Upgrade evidence bundle exporter', 'upgrade evidence bundle OK'),
    ('LU11', 'Healthcheck evidence archive retention', 'healthcheck evidence archive OK'),
]

NEXT_UPGRADE = {
    "id": "LU12",
    "title": "Healthcheck evidence index and search",
    "status": "planned",
}

def implemented_upgrade_ids() -> list[str]:
    return [item[0] for item in UPGRADES]

def validate_registry() -> list[str]:
    problems = []
    seen = set()
    for uid, title, marker in UPGRADES:
        if uid in seen:
            problems.append(f'duplicate upgrade id: {uid}')
        seen.add(uid)
        if not title:
            problems.append(f'{uid} missing title')
        if not marker:
            problems.append(f'{uid} missing healthcheck marker')
    if not NEXT_UPGRADE.get('id'):
        problems.append('missing next upgrade id')
    return problems

def main() -> int:
    problems = validate_registry()
    if problems:
        print('upgrade registry FAILED')
        for problem in problems:
            print(f'- {problem}')
        return 1
    print('upgrade registry OK')
    print('implemented: ' + ', '.join(implemented_upgrade_ids()))
    print(f"next: {NEXT_UPGRADE['id']} - {NEXT_UPGRADE['title']}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
