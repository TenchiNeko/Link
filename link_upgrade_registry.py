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
 {'healthcheck_markers': 'recovery plan dashboard latest-plan loader OK',
  'id': 'LU21',
  'status': 'implemented',
  'title': 'Recovery plan dashboard latest-plan loader'},
 {'healthcheck_markers': 'upgrade finalizer OK',
  'id': 'LU22',
  'status': 'implemented',
  'title': 'Upgrade finalizer and safe apply workflow'},
 {'healthcheck_markers': 'recovery plan dashboard latest-plan integration OK',
  'id': 'LU23',
  'status': 'implemented',
  'title': 'Recovery plan dashboard latest-plan integration'},
 {'healthcheck_markers': 'latest recovery plan dashboard execution receipts OK',
  'id': 'LU24',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard execution receipts'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt web admin route OK',
  'id': 'LU25',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt web admin route'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index OK',
  'id': 'LU26',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index web admin route OK',
  'id': 'LU27',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index web admin route'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index web admin '
                         'integration OK',
  'id': 'LU28',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index web admin integration'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'OK',
  'id': 'LU29',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'web admin route OK',
  'id': 'LU30',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt web admin '
           'route'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'web admin integration OK',
  'id': 'LU31',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt web admin '
           'integration'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index OK',
  'id': 'LU32',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence '
           'index'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index web admin route OK',
  'id': 'LU33',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'web admin route'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index web admin integration OK',
  'id': 'LU34',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'web admin integration'},
 {'healthcheck_markers': 'latest recovery plan dashboard receipt evidence index execution receipt '
                         'evidence index execution receipt OK',
  'id': 'LU35',
  'status': 'implemented',
  'title': 'Latest recovery plan dashboard receipt evidence index execution receipt evidence index '
           'execution receipt'},
 {'healthcheck_markers': 'workflow spec layer OK',
  'id': 'LU36',
  'status': 'implemented',
  'title': 'Deterministic workflow spec layer'},
 {'healthcheck_markers': 'workflow spec preflight executor OK',
  'id': 'LU37',
  'status': 'implemented',
  'title': 'Workflow spec preflight executor'},
 {'healthcheck_markers': 'workflow preflight receipt index OK',
  'id': 'LU38',
  'status': 'implemented',
  'title': 'Workflow preflight receipt index'},
 {'healthcheck_markers': 'workflow preflight receipt index web admin route OK',
  'id': 'LU39',
  'status': 'implemented',
  'title': 'Workflow preflight receipt index web admin route'},
 {'healthcheck_markers': 'workflow preflight receipt index web admin integration OK',
  'id': 'LU40',
  'status': 'implemented',
  'title': 'Workflow preflight receipt index web admin integration'},
 {'healthcheck_markers': 'workflow step executor OK',
  'id': 'LU41',
  'status': 'implemented',
  'title': 'Workflow step executor'},
 {'healthcheck_markers': 'workflow step execution receipt index OK',
  'id': 'LU42',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index'},
 {'healthcheck_markers': 'workflow step execution receipt index web admin route OK',
  'id': 'LU43',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index web admin route'},
 {'healthcheck_markers': 'workflow step execution receipt index web admin integration OK',
  'id': 'LU44',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index web admin integration'},
 {'healthcheck_markers': 'workflow step execution receipt index execution receipt OK',
  'id': 'LU45',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index execution receipt'},
 {'healthcheck_markers': 'workflow step execution receipt index execution receipt web admin route '
                         'OK',
  'id': 'LU46',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index execution receipt web admin route'},
 {'healthcheck_markers': 'workflow step execution receipt index execution receipt web admin '
                         'integration OK',
  'id': 'LU47',
  'status': 'implemented',
  'title': 'Workflow step execution receipt index execution receipt web admin integration'},
 {'healthcheck_markers': 'research archive intake miner OK',
  'id': 'LU48',
  'status': 'implemented',
  'title': 'Research archive intake miner'},
 {'healthcheck_markers': 'research archive intake miner web admin route OK',
  'id': 'LU49',
  'status': 'implemented',
  'title': 'Research archive intake miner web admin route'},
 {'healthcheck_markers': 'research archive intake miner web admin integration OK',
  'id': 'LU50',
  'status': 'implemented',
  'title': 'Research archive intake miner web admin integration'},
 {'healthcheck_markers': 'research archive intake candidate detail viewer OK',
  'id': 'LU51',
  'status': 'implemented',
  'title': 'Research archive intake candidate detail viewer'},
 {'healthcheck_markers': 'research archive candidate detail web admin integration OK',
  'id': 'LU52',
  'status': 'implemented',
  'title': 'Research archive candidate detail web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist exporter OK',
  'id': 'LU53',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist exporter'},
 {'healthcheck_markers': 'research archive candidate shortlist web admin route OK',
  'id': 'LU54',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist web admin route'},
 {'healthcheck_markers': 'research archive candidate shortlist web admin integration OK',
  'id': 'LU55',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard integration OK',
  'id': 'LU56',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin route OK',
  'id': 'LU57',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin integration OK',
  'id': 'LU58',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch OK',
  'id': 'LU59',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'integration OK',
  'id': 'LU60',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt OK',
  'id': 'LU61',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt web admin route OK',
  'id': 'LU62',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt web admin '
           'route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt web admin integration OK',
  'id': 'LU63',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt web admin '
           'integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index OK',
  'id': 'LU64',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin route OK',
  'id': 'LU65',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin integration OK',
  'id': 'LU66',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch OK',
  'id': 'LU67',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch integration OK',
  'id': 'LU68',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt OK',
  'id': 'LU69',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt web admin route OK',
  'id': 'LU70',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt web admin route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt web admin integration '
                         'OK',
  'id': 'LU71',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index OK',
  'id': 'LU72',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin route OK',
  'id': 'LU73',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin integration OK',
  'id': 'LU74',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch OK',
  'id': 'LU75',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch integration OK',
  'id': 'LU76',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch receipt OK',
  'id': 'LU77',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch receipt'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch receipt web admin route OK',
  'id': 'LU78',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch receipt web admin '
           'route'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch receipt web admin integration OK',
  'id': 'LU79',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch receipt web admin '
           'integration'},
 {'healthcheck_markers': 'research archive candidate shortlist dashboard web admin dispatch '
                         'receipt evidence index web admin dispatch receipt evidence index web '
                         'admin dispatch receipt evidence index OK',
  'id': 'LU80',
  'status': 'implemented',
  'title': 'Research archive candidate shortlist dashboard web admin dispatch receipt evidence '
           'index web admin dispatch receipt evidence index web admin dispatch receipt evidence '
           'index'},
 {'healthcheck_markers': 'self-update preflight runner OK',
  'id': 'LU82',
  'status': 'implemented',
  'title': 'Self-update preflight runner'},
 {'healthcheck_markers': 'Link-native tool registry OK',
  'id': 'LU83',
  'status': 'implemented',
  'title': 'Link-native tool registry'},
 {'healthcheck_markers': 'restricted worker profiles OK',
  'id': 'LU84',
  'status': 'implemented',
  'title': 'Restricted worker profiles'},
 {'healthcheck_markers': 'profile-aware self-update receipts OK',
  'id': 'LU85',
  'status': 'implemented',
  'title': 'Profile-aware self-update receipts'},
 {'healthcheck_markers': 'profile tool access gate OK',
  'id': 'LU86',
  'status': 'implemented',
  'title': 'Profile tool access gate'},
 {'healthcheck_markers': 'profile gate smoke coverage OK',
  'id': 'LU87',
  'status': 'implemented',
  'title': 'Profile gate smoke coverage'},
 {'commit_subject': '',
  'healthcheck_markers': 'research source inventory command OK',
  'id': 'LU88',
  'status': 'implemented',
  'title': 'Research source inventory command'},
 {'commit_subject': '',
  'healthcheck_markers': 'link grade command OK',
  'id': 'LU89',
  'status': 'implemented',
  'title': 'Permanent Link grade command'},
 {'commit_subject': '',
  'healthcheck_markers': 'guarded task-to-patch planner OK',
  'id': 'LU90',
  'status': 'implemented',
  'title': 'Guarded task-to-patch planner'},
 {'commit_subject': '',
  'healthcheck_markers': 'guarded task-to-patch executor OK',
  'id': 'LU91',
  'status': 'implemented',
  'title': 'Guarded task-to-patch executor'},
 {'commit_subject': '',
  'healthcheck_markers': 'concise task receipt format OK',
  'id': 'LU92',
  'status': 'implemented',
  'title': 'Concise task receipt format'},
 {'commit_subject': '',
  'healthcheck_markers': 'model routing profiles OK',
  'id': 'LU93',
  'status': 'implemented',
  'title': 'Model routing profiles'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard card OK',
  'id': 'LU94',
  'status': 'implemented',
  'title': 'Worker dashboard card'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard web admin route OK',
  'id': 'LU95',
  'status': 'implemented',
  'title': 'Worker dashboard web admin route'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard web admin integration OK',
  'id': 'LU96',
  'status': 'implemented',
  'title': 'Worker dashboard web admin integration'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard receipt evidence OK',
  'id': 'LU97',
  'status': 'implemented',
  'title': 'Worker dashboard receipt evidence'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard evidence index OK',
  'id': 'LU98',
  'status': 'implemented',
  'title': 'Worker dashboard evidence index'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard evidence index web admin route OK',
  'id': 'LU99',
  'status': 'implemented',
  'title': 'Worker dashboard evidence index web admin route'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard evidence index web admin integration OK',
  'id': 'LU100',
  'status': 'implemented',
  'title': 'Worker dashboard evidence index web admin integration'},
 {'commit_subject': '',
  'healthcheck_markers': 'worker dashboard evidence index execution receipt OK',
  'id': 'LU101',
  'status': 'implemented',
  'title': 'Worker dashboard evidence index execution receipt'}]

NEXT_UPGRADE = {'id': 'LU102', 'status': 'planned', 'title': 'Worker dashboard evidence index execution receipt web admin route'}


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
