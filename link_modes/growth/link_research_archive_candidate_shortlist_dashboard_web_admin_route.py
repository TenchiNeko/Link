#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

import link_research_archive_candidate_shortlist_dashboard_integration as dashboard
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin route OK"
ROUTE_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_route"
DATA_LINK_ROUTE = "research-archive-candidate-shortlist-dashboard-web-admin-route"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parents[2] / ".link_research_intake"

TRIGGERS = (
    "research archive candidate shortlist dashboard web admin route",
    "research candidate shortlist dashboard web admin route",
    "candidate shortlist dashboard web admin route",
    "research archive candidate shortlist dashboard route",
    "show research shortlist dashboard web admin",
    "view research shortlist dashboard web admin",
    "research shortlist dashboard route",
)


def matches_research_candidate_shortlist_dashboard_web_admin_route_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    if not lowered:
        return False

    if any(trigger in lowered for trigger in TRIGGERS):
        return True

    matcher = getattr(dashboard, "matches_research_candidate_shortlist_dashboard_prompt", None)
    if callable(matcher):
        try:
            return bool(matcher(prompt)) and "dashboard" in lowered
        except Exception:
            return False

    return False


def normalize_research_candidate_shortlist_dashboard_web_admin_route_prompt(prompt: str) -> str:
    value = " ".join((prompt or "").strip().split())
    if value:
        return value
    return "show research archive candidate shortlist dashboard web admin route"


def _call_dashboard_response(
    prompt: str,
    *,
    intake_dir: Path,
    limit: int,
    preview_limit: int,
    write_outputs: bool,
    json_requested: bool,
) -> dict[str, Any]:
    builder = getattr(dashboard, "build_research_candidate_shortlist_dashboard_response")

    kwargs: dict[str, Any] = {
        "intake_dir": Path(intake_dir),
        "limit": limit,
        "preview_limit": preview_limit,
        "write_outputs": write_outputs,
        "json_requested": json_requested,
    }

    signature = inspect.signature(builder)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }

    response = builder(prompt, **accepted)
    if not isinstance(response, dict):
        return {
            "ok": False,
            "matched": False,
            "kind": ROUTE_KIND,
            "marker": MARKER,
            "error": "dashboard response was not a dict",
        }

    return dict(response)


def _decorate_html(response: dict[str, Any]) -> None:
    html = str(response.get("html") or "")
    if not html:
        return

    if DATA_LINK_ROUTE not in html:
        html = html.replace(
            "<section",
            f'<section data-link-route="{DATA_LINK_ROUTE}"',
            1,
        ) if "<section" in html else (
            f'<section data-link-route="{DATA_LINK_ROUTE}" '
            f'data-link-destructive="false">{html}</section>'
        )

    if 'data-link-destructive="false"' not in html:
        html = html.replace(
            "<section",
            '<section data-link-destructive="false"',
            1,
        ) if "<section" in html else (
            f'<section data-link-route="{DATA_LINK_ROUTE}" '
            f'data-link-destructive="false">{html}</section>'
        )

    # Preserve the LU56 validator contract in the route output too.
    if "<table>" not in html and "<table" in html:
        html = html.replace(html[html.find("<table"):html.find(">", html.find("<table")) + 1], "<table>", 1)

    response["html"] = html


def build_research_candidate_shortlist_dashboard_web_admin_route_response(
    prompt: str,
    *,
    intake_dir: Path = DEFAULT_INTAKE_DIR,
    limit: int = 10,
    preview_limit: int = 500,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_dashboard_web_admin_route_prompt(prompt)
    matched = matches_research_candidate_shortlist_dashboard_web_admin_route_prompt(normalized_prompt)

    response = _call_dashboard_response(
        normalized_prompt,
        intake_dir=Path(intake_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    response["ok"] = bool(response.get("ok", False)) and matched
    response["matched"] = matched
    response["kind"] = ROUTE_KIND
    response["route_kind"] = ROUTE_KIND
    response["marker"] = MARKER
    response["route_marker"] = MARKER
    response["data_link_route"] = DATA_LINK_ROUTE
    response["normalized_prompt"] = normalized_prompt
    response["json_requested"] = bool(json_requested)

    _decorate_html(response)
    return response


def validate_research_candidate_shortlist_dashboard_web_admin_route() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_route_response(
            "show research archive candidate shortlist dashboard web admin route",
            intake_dir=intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dashboard web admin route response should be ok")
        if not response.get("matched"):
            failures.append("dashboard web admin route response should be matched")
        if response.get("route_marker") != MARKER:
            failures.append("dashboard web admin route marker mismatch")
        if response.get("data_link_route") != DATA_LINK_ROUTE:
            failures.append("dashboard web admin route data-link mismatch")

        html_text = response.get("html") or ""
        if DATA_LINK_ROUTE not in html_text:
            failures.append("dashboard web admin route html missing data-link route")
        if "Research archive candidate shortlist" not in html_text:
            failures.append("dashboard web admin route html missing title")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dashboard web admin route should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dashboard web admin route html missing candidate table")

        if int(response.get("shortlist_count") or 0) < 1:
            failures.append("dashboard web admin route should include shortlist candidates")

        paths = response.get("paths") or {}
        if not isinstance(paths, dict) or not paths.get("json"):
            failures.append("dashboard web admin route response missing JSON output path")
        if not isinstance(paths, dict) or not paths.get("report"):
            failures.append("dashboard web admin route response missing report output path")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_route()
    if failures:
        print("research archive candidate shortlist dashboard web admin route FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research archive candidate shortlist dashboard web admin route."
    )
    parser.add_argument("prompt", nargs="*", help="Prompt text to route.")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=500)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_requested")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    prompt = " ".join(args.prompt).strip() or "show research archive candidate shortlist dashboard web admin route"
    response = build_research_candidate_shortlist_dashboard_web_admin_route_response(
        prompt,
        intake_dir=Path(args.intake_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=not args.no_write,
        json_requested=args.json_requested,
    )

    if args.json_requested:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html") or json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
