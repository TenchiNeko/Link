#!/usr/bin/env python3
"""Factory team runner.

Examples:
  python3 link_factory_team.py roster
  python3 link_factory_team.py models --offline
  python3 link_factory_team.py models --validate
  python3 link_factory_team.py run --project growth_lab --goal "Build a 7-day growth plan" --tier cheap --dry-run
  python3 link_factory_team.py run --project growth_lab --goal "Build a 7-day growth plan" --tier cheap --execute-models
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from factory.team_registry import TEAM, PIPELINES, model_ids, role_dicts, tier_names
from factory.openrouter_team import validate_model_ids
from factory.factory_pipeline import run_pipeline


def cmd_roster(args) -> int:
    for role in TEAM.values():
        print(f"{role.role_id}: {role.title} | {role.department} | {role.model}")
    return 0


def cmd_models(args) -> int:
    ids = model_ids()
    print("Configured model IDs:")
    for model in ids:
        print(f"- {model}")

    if args.validate:
        print("\nValidating against OpenRouter catalog...")
        result = validate_model_ids(ids)
        print(json.dumps(result, indent=2))
        return 0 if not result["missing"] else 2

    print("\nOffline mode only. Use --validate to pull OpenRouter /models.")
    return 0


def cmd_run(args) -> int:
    result = run_pipeline(
        project=args.project,
        goal=args.goal,
        tier=args.tier,
        execute_models=args.execute_models,
        max_tokens=args.max_tokens,
    )
    print("Factory run created")
    print(f"run_dir: {result['run_dir']}")
    print(f"manifest: {result['manifest']}")
    print(f"summary: {result['summary']}")
    print(f"execute_models: {result['execute_models']}")
    print("roles:")
    for role_id in result["roles"]:
        print(f"- {role_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Link Factory Team - OpenRouter model team pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("roster", help="Show factory roles and assigned models")
    p.set_defaults(func=cmd_roster)

    p = sub.add_parser("models", help="Show or validate configured OpenRouter models")
    p.add_argument("--offline", action="store_true", help="Only print configured models")
    p.add_argument("--validate", action="store_true", help="Validate model IDs against OpenRouter /models")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("run", help="Run a draft-only factory pipeline")
    p.add_argument("--project", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--tier", choices=sorted(PIPELINES), default="cheap")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Do not call models; create a simulated run")
    group.add_argument("--execute-models", action="store_true", help="Actually call OpenRouter models")
    p.add_argument("--max-tokens", type=int, default=1600)
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
