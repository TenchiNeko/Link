#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "research archive intake miner web admin integration OK"


def route_research_archive_intake_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_research_archive_intake_response(
    intake_dir: Path | None = None,
    *,
    prompt: str = "show research archive intake json",
) -> dict[str, Any]:
    from link_research_archive_intake_web_admin import (
        build_research_archive_intake_web_admin_response,
    )

    return build_research_archive_intake_web_admin_response(prompt, intake_dir)


def _write_sample_intake(intake_dir: Path) -> Path:
    from link_research_archive_intake_web_admin import (
        AGENT_JOBS_NAME,
        CANDIDATE_FILES_NAME,
        DIRECTORY_MAP_NAME,
        JSON_NAME,
        LATEST_NAME,
        REPORT_NAME,
    )

    run_dir = intake_dir / "research-mining-integration-test"
    run_dir.mkdir(parents=True, exist_ok=True)
    (intake_dir / LATEST_NAME).write_text(run_dir.name, encoding="utf-8")

    mining_result = {
        "kind": "link_research_archive_mining_result",
        "marker": "research archive intake miner OK",
        "status": "ok",
        "ok": True,
        "created_at": "2026-05-24T00:00:00+00:00",
        "sources": [
            {
                "type": "zip",
                "source": "research/Research.zip",
                "extracted_count": 4,
                "skipped_count": 0,
            }
        ],
        "findings": [],
        "agent_jobs": [],
        "inputs": ["research/Research.zip"],
    }

    (run_dir / JSON_NAME).write_text(json.dumps(mining_result, indent=2), encoding="utf-8")
    (run_dir / REPORT_NAME).write_text(
        "# Link research archive mining report\n\n- Status: `ok`\n",
        encoding="utf-8",
    )
    (run_dir / AGENT_JOBS_NAME).write_text("[]\n", encoding="utf-8")
    (run_dir / DIRECTORY_MAP_NAME).write_text(
        "# Research intake directory map\n\n"
        "- Total files: `4`\n"
        "- Candidate files with keyword hits: `2`\n\n"
        "## Top candidate files\n"
        "- score `10` `Research/Research/src/screens/REPL.tsx`\n",
        encoding="utf-8",
    )
    (run_dir / CANDIDATE_FILES_NAME).write_text(
        "Research/Research/src/screens/REPL.tsx\n"
        "Research/Research/src/tools/BashTool/bashPermissions.ts\n",
        encoding="utf-8",
    )

    return run_dir


def validate_research_archive_intake_web_admin_integration() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        run_dir = _write_sample_intake(intake_dir)

        direct = build_integrated_research_archive_intake_response(
            intake_dir,
            prompt="show research archive intake json",
        )

        if not direct.get("ok"):
            problems.append("direct integrated response should be ok")
        if not direct.get("matched"):
            problems.append("direct integrated response should be matched")
        if not direct.get("json_requested"):
            problems.append("direct integrated response should detect json")
        if not direct.get("non_destructive"):
            problems.append("direct integrated response should be non-destructive")
        if direct.get("latest_run") is None:
            problems.append("direct integrated response missing latest run")
        if run_dir.name not in str(direct.get("latest_run")):
            problems.append("direct integrated response latest run mismatch")

        summary = direct.get("summary")
        if not isinstance(summary, dict):
            problems.append("direct integrated response missing summary")
        else:
            if summary.get("extracted_count") != 4:
                problems.append("direct integrated response extracted count mismatch")
            if summary.get("candidate_file_count") != 2:
                problems.append("direct integrated response candidate count mismatch")

        rendered = str(direct.get("html") or "")
        if "Research archive intake miner" not in rendered:
            problems.append("direct integrated HTML missing title")
        if "research-archive-intake" not in rendered:
            problems.append("direct integrated HTML missing card marker")
        if 'data-link-destructive="false"' not in rendered:
            problems.append("direct integrated HTML missing non-destructive marker")

    routed = route_research_archive_intake_prompt("show research archive intake json")
    if not routed:
        problems.append("main web admin route returned no output")
    else:
        joined = "\n".join(routed)
        if "research_archive_intake_web_admin" not in joined:
            problems.append("main web admin route missing research archive intake payload kind")
        if "research archive intake" not in joined.lower():
            problems.append("main web admin route missing research archive intake title")
        if "non_destructive" not in joined:
            problems.append("main web admin route missing non_destructive contract")

    unrelated = route_research_archive_intake_prompt("show recovery plan dashboard json")
    if not unrelated:
        problems.append("main web admin route should still handle recovery dashboard prompts")
    elif "recovery" not in "\n".join(unrelated).lower():
        problems.append("recovery dashboard route appears broken after research integration")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research archive intake miner web admin integration."
    )
    parser.add_argument("--intake-dir")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_research_archive_intake_web_admin_integration()
        if problems:
            print("research archive intake miner web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    response = build_integrated_research_archive_intake_response(
        Path(args.intake_dir) if args.intake_dir else None,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
