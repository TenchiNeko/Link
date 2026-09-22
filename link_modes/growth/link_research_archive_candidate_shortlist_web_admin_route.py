#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from .link_research_archive_candidate_shortlist_exporter import (
    DEFAULT_INTAKE_DIR,
    _write_self_test_intake,
    build_research_archive_candidate_shortlist_response,
)


MARKER = "research archive candidate shortlist web admin route OK"

TRIGGERS = (
    "research archive candidate shortlist",
    "research candidate shortlist",
    "candidate shortlist",
    "show research shortlist",
    "view research shortlist",
    "research archive shortlist",
    "candidate shortlist web admin",
)


def matches_research_candidate_shortlist_web_admin_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    return any(trigger in lowered for trigger in TRIGGERS)


def normalize_research_candidate_shortlist_prompt(prompt: str | None = None) -> str:
    text = (prompt or "").strip()
    if not text:
        return "show research archive candidate shortlist"
    if matches_research_candidate_shortlist_web_admin_prompt(text):
        return text
    return f"show research archive candidate shortlist {text}"


def build_research_candidate_shortlist_web_admin_route_response(
    prompt: str | None = None,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    *,
    limit: int = 10,
    preview_limit: int = 600,
    write_outputs: bool = True,
    json_requested: bool = True,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_prompt(prompt)
    matched = matches_research_candidate_shortlist_web_admin_prompt(normalized_prompt)

    if not matched:
        return {
            "ok": False,
            "status": "not_matched",
            "kind": "research_archive_candidate_shortlist_web_admin_route",
            "matched": False,
            "prompt": prompt or "",
            "normalized_prompt": normalized_prompt,
            "non_destructive": True,
            "data_link_card": "research-archive-candidate-shortlist",
        }

    response = build_research_archive_candidate_shortlist_response(
        Path(intake_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=json_requested,
    )

    response["kind"] = "research_archive_candidate_shortlist_web_admin_route"
    response["source_kind"] = "research_archive_candidate_shortlist_exporter"
    response["matched"] = True
    response["prompt"] = prompt or ""
    response["normalized_prompt"] = normalized_prompt
    response["non_destructive"] = True
    response["data_link_card"] = "research-archive-candidate-shortlist"
    return response


def validate_research_candidate_shortlist_web_admin_route(*args: Any, **kwargs: Any) -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_web_admin_route_response(
            "show research archive candidate shortlist web admin",
            intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )

        records = response.get("records", [])

        if not response.get("ok"):
            failures.append("route response should be ok")
        if not response.get("matched"):
            failures.append("route response should be matched")
        if response.get("kind") != "research_archive_candidate_shortlist_web_admin_route":
            failures.append(f"wrong route kind: {response.get('kind')}")
        if response.get("candidate_count") != 3:
            failures.append(f"candidate_count should be 3, got {response.get('candidate_count')}")
        if response.get("shortlist_count") != 2:
            failures.append(f"shortlist_count should be 2, got {response.get('shortlist_count')}")
        if len(records) != 2:
            failures.append(f"route should return two records, got {len(records)}")
        if records and records[0].get("score") != 870:
            failures.append(f"first route candidate score mismatch: {records[0].get('score')}")
        if records and records[0].get("keyword_counts", {}).get("agent") != 211:
            failures.append(f"first route candidate keyword counts missing: {records[0].get('keyword_counts')}")
        if "html" not in response:
            failures.append("route response missing html")
        if response.get("data_link_card") != "research-archive-candidate-shortlist":
            failures.append("route response missing expected data_link_card")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_web_admin_route()
    if failures:
        print("research archive candidate shortlist web admin route FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research archive candidate shortlist web admin route")
    parser.add_argument("prompt", nargs="*", help="Prompt or shorthand selector")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=600)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    response = build_research_candidate_shortlist_web_admin_route_response(
        " ".join(args.prompt),
        Path(args.intake_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=True,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(MARKER if response.get("ok") else "research archive candidate shortlist web admin route FAILED")
        print(response.get("html", ""))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
