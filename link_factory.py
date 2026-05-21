#!/usr/bin/env python3
from __future__ import annotations

import argparse

from factory.workflow import plan, report, run_today


def main() -> int:
    parser = argparse.ArgumentParser(description="Link Factory Mode - Phase 1 non-executing project manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Create a non-executing project plan work order")
    p_plan.add_argument("--project", required=True)
    p_plan.add_argument("--goal", required=True)

    p_run = sub.add_parser("run-today", help="Show queued work; execution disabled in Phase 1")
    p_run.add_argument("--project", required=True)

    p_report = sub.add_parser("report", help="Show project factory report")
    p_report.add_argument("--project", required=True)

    args = parser.parse_args()

    if args.command == "plan":
        print(plan(args.project, args.goal))
    elif args.command == "run-today":
        print(run_today(args.project))
    elif args.command == "report":
        print(report(args.project))
    else:
        parser.error(f"Unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
