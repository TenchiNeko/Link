#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Any

from link_common import (
    ROOT,
    full_head_commit,
    git_dirty,
    head_commit,
    json_print,
    latest_engine_report,
    run_cmd,
    safe_latest_commit,
    scrub_text,
)
import link_agents
import link_config_conflicts
import link_rules
import link_status
import link_loop_report


def collect() -> dict[str, Any]:
    dirty = git_dirty()
    latest = latest_engine_report()
    loop_summary = None
    if latest:
        try:
            loop_summary = link_loop_report.build_report(latest)
        except Exception as exc:
            loop_summary = {"error": str(exc)}

    web_src = (ROOT / "link_web.py").read_text(encoding="utf-8") if (ROOT / "link_web.py").exists() else ""
    engine_src = (ROOT / "link_engine.py").read_text(encoding="utf-8") if (ROOT / "link_engine.py").exists() else ""

    web_checks = {
        "routes_through_engine": 'str(ROOT / "link_engine.py")' in web_src,
        "has_run_status_endpoint": 'parsed.path.startswith("/api/run/")' in web_src,
        "has_status_poller": "pollRunStatus" in web_src,
        "has_engine_report_fallback": "find_engine_report_for_run" in web_src,
        "fake_worktree_toggle_absent": 'id="worktree"' not in web_src and "Use worktree" not in web_src,
    }

    engine_checks = {
        "expected_change_guard": "expected_changed_files" in engine_src and "min_changed_files" in engine_src,
        "live_report_writer": "_write_live_report" in engine_src and "self._write_live_report(state)" in engine_src,
        "auto_restore_flag": "--auto-restore-on-failure" in engine_src,
    }

    return {
        "root": str(ROOT),
        "git": {
            "head": head_commit(),
            "head_full": full_head_commit(),
            "safe_link_latest": safe_latest_commit(),
            "dirty": dirty,
            "dirty_count": len(dirty),
        },
        "web": web_checks,
        "engine": engine_checks,
        "latest_engine_report": latest,
        "latest_failure_summary": loop_summary,
        "rules_critique": link_rules.critique_rules(link_rules.effective_rules()),
        "agents": link_agents.collect(),
        "endpoint_status": link_status.collect_endpoints(),
        "config_conflicts": link_config_conflicts.collect(),
        "healthcheck": run_cmd(["python3", "link_healthcheck.py"], timeout=60),
    }


def print_human(data: dict[str, Any]) -> None:
    print("LINK DOCTOR")
    print(f"repo: {data['root']}")
    print(f"HEAD: {data['git']['head']}   safe-link-latest: {data['git']['safe_link_latest']}")
    print(f"dirty files: {data['git']['dirty_count']}")

    print("\nWeb:")
    for key, value in data["web"].items():
        print(f"- {key}: {'OK' if value else 'FAIL'}")

    print("\nEngine:")
    for key, value in data["engine"].items():
        print(f"- {key}: {'OK' if value else 'FAIL'}")

    latest = data.get("latest_engine_report")
    print("\nLatest engine run:")
    if latest:
        print(f"- run_id: {latest.get('run_id')}")
        print(f"- status: {latest.get('status')}")
        print(f"- phase: {latest.get('phase')}")
        print(f"- exit_code: {latest.get('exit_code')}")
        print(f"- report: {latest.get('_path') or latest.get('report_path')}")
    else:
        print("- none found")

    summary = data.get("latest_failure_summary")
    print("\nLatest failure summary:")
    if summary:
        print(f"- failure_type: {summary.get('failure_type')}")
        print(f"- phase: {summary.get('phase')}")
        print(f"- safe_to_retry: {summary.get('safe_to_retry')}")
        obs = summary.get("last_successful_observation")
        if obs:
            print(f"- last_successful_observation: {scrub_text(str(obs))[:300]}")
        recs = summary.get("recommended_next_action") or []
        for rec in recs[:5]:
            print(f"  - {rec}")
    else:
        print("- none")

    findings = data["rules_critique"]["findings"]
    print("\nRule critique:")
    for finding in findings[:10]:
        print(f"- {finding['severity']}: {finding['path']} — {finding['message']}")

    conflicts = data["config_conflicts"]["conflicts"]
    print(f"\nConfig conflicts: {len(conflicts)}")
    for item in conflicts[:10]:
        print(f"- {item['key']}: {', '.join(item['scopes'])}")

    health = data["healthcheck"]
    print(f"\nHealthcheck: {'OK' if health['ok'] else 'FAIL'}")
    if not health["ok"]:
        print(health.get("stderr") or health.get("stdout") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Link diagnostics dashboard.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = collect()
    if args.json:
        json_print(data)
    else:
        print_human(data)

    bad = []
    bad += [k for k, v in data["web"].items() if not v]
    bad += [k for k, v in data["engine"].items() if not v]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
