#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "research archive candidate detail web admin integration OK"


def route_research_archive_candidate_detail_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_research_archive_candidate_detail_response(
    intake_dir: Path | None = None,
    *,
    prompt: str = "show research archive candidate detail json top 1",
    candidate: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    from link_research_archive_candidate_detail_viewer import (
        build_research_archive_candidate_detail_response,
    )

    return build_research_archive_candidate_detail_response(
        prompt,
        intake_dir,
        candidate=candidate,
        limit=limit,
    )


def _write_sample_intake(intake_dir: Path) -> tuple[Path, str]:
    from link_research_archive_candidate_detail_viewer import (
        CANDIDATE_FILES_NAME,
        LATEST_NAME,
    )

    run_dir = intake_dir / "research-mining-candidate-integration-test"
    extracted = run_dir / "extracted"
    candidate_rel = "Research/Research/src/tools/BashTool/bashPermissions.ts"
    candidate_path = extracted / candidate_rel
    candidate_path.parent.mkdir(parents=True, exist_ok=True)

    candidate_path.write_text(
        "export function canRunCommand(command: string) {\\n"
        "  // TODO: inspect guard policy context for delegated agent command workflow\\n"
        "  return command.startsWith('git status')\\n"
        "}\\n",
        encoding="utf-8",
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    (intake_dir / LATEST_NAME).write_text(run_dir.name, encoding="utf-8")
    (run_dir / CANDIDATE_FILES_NAME).write_text(candidate_rel + "\\n", encoding="utf-8")

    return run_dir, candidate_rel


def validate_research_archive_candidate_detail_web_admin_integration() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        run_dir, candidate_rel = _write_sample_intake(intake_dir)

        direct = build_integrated_research_archive_candidate_detail_response(
            intake_dir,
            prompt="show research archive candidate detail json",
            candidate=candidate_rel,
            limit=6000,
        )

        if not direct.get("ok"):
            problems.append("direct integrated response should be ok")
        if not direct.get("matched"):
            problems.append("direct integrated response should be matched")
        if not direct.get("json_requested"):
            problems.append("direct integrated response should detect json")
        if not direct.get("non_destructive"):
            problems.append("direct integrated response should be non-destructive")
        if direct.get("candidate") != candidate_rel:
            problems.append("direct integrated response selected wrong candidate")
        if run_dir.name not in str(direct.get("latest_run")):
            problems.append("direct integrated latest run mismatch")
        if "canRunCommand" not in str(direct.get("content_preview") or ""):
            problems.append("direct integrated preview missing source content")

        rendered = str(direct.get("html") or "")
        if "Research archive candidate detail" not in rendered:
            problems.append("direct integrated HTML missing title")
        if "research-archive-candidate-detail" not in rendered:
            problems.append("direct integrated HTML missing card marker")
        if 'data-link-destructive="false"' not in rendered:
            problems.append("direct integrated HTML missing non-destructive marker")

        from link_research_archive_candidate_detail_viewer import (
            matches_research_candidate_detail_prompt,
            normalize_direct_candidate_detail_prompt,
        )

        normalized = normalize_direct_candidate_detail_prompt("top 1")
        if not matches_research_candidate_detail_prompt(normalized):
            problems.append("direct CLI shorthand top 1 should normalize to matched prompt")

        shorthand = build_integrated_research_archive_candidate_detail_response(
            intake_dir,
            prompt=normalized + " json",
            limit=4000,
        )
        if not shorthand.get("ok"):
            problems.append("normalized shorthand response should be ok")
        if not shorthand.get("matched"):
            problems.append("normalized shorthand response should be matched")
        if shorthand.get("candidate") != candidate_rel:
            problems.append(
                f"normalized shorthand selected wrong candidate: {shorthand.get('candidate')}"
            )

    routed = route_research_archive_candidate_detail_prompt(
        "show research archive candidate detail json top 1"
    )
    if not routed:
        problems.append("main web admin route returned no output")
    else:
        joined = "\\n".join(routed)
        if "research_archive_candidate_detail_viewer" not in joined:
            problems.append("main web admin route missing candidate detail payload kind")
        if "research archive candidate detail" not in joined.lower():
            problems.append("main web admin route missing candidate detail title")
        if "non_destructive" not in joined:
            problems.append("main web admin route missing non_destructive contract")

    recovery = route_research_archive_candidate_detail_prompt("show recovery plan dashboard json")
    if not recovery:
        problems.append("main web admin route should still handle recovery dashboard prompts")
    elif "recovery" not in "\\n".join(recovery).lower():
        problems.append("recovery dashboard route appears broken after candidate detail integration")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research archive candidate detail web admin integration."
    )
    parser.add_argument("--intake-dir")
    parser.add_argument("--candidate")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_research_archive_candidate_detail_web_admin_integration()
        if problems:
            print("research archive candidate detail web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    response = build_integrated_research_archive_candidate_detail_response(
        Path(args.intake_dir) if args.intake_dir else None,
        candidate=args.candidate,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
