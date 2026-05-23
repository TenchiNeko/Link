#!/usr/bin/env python3
from __future__ import annotations

UPGRADES = [{'commit_subject': '',
  'healthcheck_markers': ['context truncation fixture OK'],
  'id': 'LU01',
  'status': 'implemented',
  'title': 'Context manifest and truncation hardening'},
 {'commit_subject': '',
  'healthcheck_markers': ['capability gate OK'],
  'id': 'LU02',
  'status': 'implemented',
  'title': 'Unified capability safety gate'},
 {'commit_subject': '',
  'healthcheck_markers': ['execution receipts OK'],
  'id': 'LU03',
  'status': 'implemented',
  'title': 'Execution receipts audit trail'},
 {'commit_subject': '',
  'healthcheck_markers': ['execution snapshots OK'],
  'id': 'LU04',
  'status': 'implemented',
  'title': 'Rollback execution snapshots'},
 {'commit_subject': '',
  'healthcheck_markers': ['upgrade registry OK'],
  'id': 'LU05',
  'status': 'implemented',
  'title': 'Upgrade registry'},
 {'commit_subject': '',
  'healthcheck_markers': ['planner acceptance contract OK'],
  'id': 'LU06',
  'status': 'implemented',
  'title': 'Planner-to-implementation acceptance contract'},
 {'commit_subject': '',
  'healthcheck_markers': ['upgrade status badges OK'],
  'id': 'LU07',
  'status': 'implemented',
  'title': 'Implementation status dashboard badges'},
 {'commit_subject': '',
  'healthcheck_markers': ['upgrade diff receipt cross-check OK'],
  'id': 'LU08',
  'status': 'implemented',
  'title': 'Upgrade diff/receipt cross-check'},
 {'commit_subject': '',
  'healthcheck_markers': ['qa repair routing contract OK'],
  'id': 'LU09',
  'status': 'implemented',
  'title': 'Automated QA repair routing contract'},
 {'commit_subject': '',
  'healthcheck_markers': ['upgrade evidence bundle OK'],
  'id': 'LU10',
  'status': 'implemented',
  'title': 'Upgrade evidence bundle exporter'},
 {'commit_subject': '',
  'healthcheck_markers': ['healthcheck evidence archive OK'],
  'id': 'LU11',
  'status': 'implemented',
  'title': 'Healthcheck evidence archive retention'},
 {'commit_subject': 'feat: add healthcheck evidence index and search LU12',
  'healthcheck_markers': ['healthcheck evidence index OK'],
  'id': 'LU12',
  'status': 'implemented',
  'title': 'Healthcheck evidence index and search'},
 {'commit_subject': 'feat: add evidence-aware rollback advisor LU13',
  'healthcheck_markers': ['evidence rollback advisor OK'],
  'id': 'LU13',
  'status': 'implemented',
  'title': 'Evidence-aware rollback advisor'},
 {'commit_subject': 'feat: add rollback advisor dashboard integration LU14',
  'healthcheck_markers': ['rollback advisor dashboard OK'],
  'id': 'LU14',
  'status': 'implemented',
  'title': 'Rollback advisor dashboard integration'},
 {'commit_subject': 'feat: add rollback advisor CLI command integration LU15',
  'healthcheck_markers': ['rollback advisor CLI OK'],
  'id': 'LU15',
  'status': 'implemented',
  'title': 'Rollback advisor CLI command integration'},
 {'commit_subject': 'feat: add rollback advisor web admin command routing LU16',
  'healthcheck_markers': ['rollback advisor web admin route OK'],
  'id': 'LU16',
  'status': 'implemented',
  'title': 'Rollback advisor web admin command routing'},
 {'commit_subject': 'feat: add rollback advisor guarded recovery plan exporter LU17',
  'healthcheck_markers': ['rollback recovery plan exporter OK'],
  'id': 'LU17',
  'status': 'implemented',
  'title': 'Rollback advisor guarded recovery plan exporter'},
 {'commit_subject': 'feat: add rollback recovery plan web admin route LU18',
  'healthcheck_markers': ['rollback recovery plan web admin route OK'],
  'id': 'LU18',
  'status': 'implemented',
  'title': 'Rollback recovery plan web admin route'},
 {'commit_subject': 'feat: add recovery plan dashboard card LU19',
  'healthcheck_markers': ['recovery plan dashboard card OK'],
  'id': 'LU19',
  'status': 'implemented',
  'title': 'Recovery plan dashboard card'},
 {'commit_subject': 'feat: add recovery plan dashboard web admin integration LU20',
  'healthcheck_markers': ['recovery plan dashboard web admin integration OK'],
  'id': 'LU20',
  'status': 'implemented',
  'title': 'Recovery plan dashboard web admin integration'},
 {'id': 'LU21',
  'status': 'implemented',
  'title': 'Recovery plan dashboard latest-plan loader',
  'healthcheck_markers': 'recovery plan dashboard latest-plan loader OK'},
 {'id': 'LU22',
  'status': 'implemented',
  'title': 'Upgrade finalizer and safe apply workflow',
  'healthcheck_markers': 'upgrade finalizer OK'},
 {'id': 'LU23',
  'status': 'implemented',
  'title': 'Recovery plan dashboard latest-plan integration',
  'healthcheck_markers': 'recovery plan dashboard latest-plan integration OK'},
 {'id': 'LU24',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard execution receipts',
  'healthcheck_markers': 'latest recovery plan dashboard execution receipts OK'},
 {'id': 'LU25',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt web admin route',
  'healthcheck_markers': 'latest recovery plan dashboard receipt web admin route OK'},
 {'id': 'LU26',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index OK'},
 {'id': 'LU27',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index web admin route',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index web admin route '
                         'OK'},
 {'id': 'LU28',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index web admin integration',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index web admin '
                         'integration OK'},
 {'id': 'LU29',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'OK'},
 {'id': 'LU30',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt web admin '
           'route',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'web admin route OK'},
 {'id': 'LU31',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt web admin '
           'integration',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'web admin integration OK'},
 {'id': 'LU32',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index OK'},
 {'id': 'LU33',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'web admin route',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index web admin route OK'},
 {'id': 'LU34',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'web admin integration',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index web admin integration OK'},
 {'id': 'LU35',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'execution receipt',
  'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index execution receipt OK'},
 {'id': 'LU36',
  'status': 'implemented',
  'title': 'Deterministic workflow spec layer',
  'healthcheck_markers': 'workflow spec layer OK'}]

NEXT_UPGRADE = {'id': 'LU37', 'status': 'planned', 'title': 'Workflow spec preflight executor'}


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
