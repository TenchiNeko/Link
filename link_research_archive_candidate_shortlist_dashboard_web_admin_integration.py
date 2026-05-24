#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

import link_research_archive_candidate_shortlist_dashboard_web_admin_route as route
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin integration OK"
INTEGRATION_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_integration"
DATA_LINK_INTEGRATION = "research-archive-candidate-shortlist-dashboard-web-admin-integration"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parent / ".link_research_intake"

TRIGGERS = (
    "research archive candidate shortlist dashboard web admin integration",
    "research candidate shortlist dashboard web admin integration",
    "candidate shortlist dashboard web admin integration",
    "research archive candidate shortlist dashboard web admin",
    "show research shortlist dashboard web admin",
    "view research shortlist dashboard web admin",
)


def matches_research_candidate_shortlist_dashboard_web_admin_integration_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())

    if any(trigger in lowered for trigger in TRIGGERS):
        return True

    matcher = getattr(route, "matches_research_candidate_shortlist_dashboard_web_admin_route_prompt", None)
    if callable(matcher):
        return bool(matcher(prompt))

    return False


def normalize_research_candidate_shortlist_dashboard_web_admin_integration_prompt(prompt: str) -> str:
    normalizer = getattr(route, "normalize_research_candidate_shortlist_dashboard_web_admin_route_prompt", None)
    if callable(normalizer):
        return str(normalizer(prompt))

    return " ".join((prompt or "").split())


def _route_builder() -> Callable[..., dict[str, Any]]:
    preferred = (
        "build_research_candidate_shortlist_dashboard_web_admin_route_response",
        "build_research_archive_candidate_shortlist_dashboard_web_admin_route_response",
    )

    for name in preferred:
        value = getattr(route, name, None)
        if callable(value):
            return value

    for name in dir(route):
        if name.startswith("build_") and name.endswith("_response"):
            value = getattr(route, name)
            if callable(value):
                return value

    raise RuntimeError("Could not find LU57 route response builder")


def _call_builder(builder: Callable[..., dict[str, Any]], prompt: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(builder)
    params = signature.parameters

    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in params
    }

    try:
        response = builder(prompt, **accepted)
    except TypeError:
        if "prompt" in params:
            accepted["prompt"] = prompt
        response = builder(**accepted)

    if not isinstance(response, dict):
        raise TypeError("LU57 route builder did not return a dict")

    return response


def _find_records(payload: dict[str, Any]) -> list[Any]:
    for key in ("shortlist", "records", "candidates", "top_candidates", "candidate_shortlist"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for key in ("response", "route_response", "dashboard_response", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            found = _find_records(value)
            if found:
                return found

    return []


def _ensure_literal_table(response: dict[str, Any]) -> None:
    html_text = str(response.get("html") or "")

    if "<table>" in html_text:
        return

    records = _find_records(response)
    rows: list[str] = []

    for index, item in enumerate(records[:10], 1):
        if isinstance(item, dict):
            candidate = item.get("candidate") or item.get("path") or item.get("file") or ""
            score = item.get("score", "")
        else:
            candidate = str(item)
            score = ""

        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{candidate}</code></td>"
            f"<td>{score}</td>"
            "</tr>"
        )

    if not rows:
        rows.append("<tr><td colspan=\"3\">No candidates found.</td></tr>")

    table = (
        "<table>"
        "<thead><tr><th>Rank</th><th>Candidate</th><th>Score</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    if "</section>" in html_text:
        html_text = html_text.replace("</section>", table + "</section>", 1)
    else:
        html_text = html_text + table

    response["html"] = html_text


def _ensure_integration_html(response: dict[str, Any]) -> None:
    html_text = str(response.get("html") or "")

    if DATA_LINK_INTEGRATION not in html_text:
        html_text = (
            f"<section data-link-card=\"{DATA_LINK_INTEGRATION}\" data-link-destructive=\"false\">"
            "<h2>Research archive candidate shortlist dashboard web admin integration</h2>"
            f"<p>{MARKER}</p>"
            f"{html_text}"
            "</section>"
        )

    response["html"] = html_text
    _ensure_literal_table(response)


def build_research_candidate_shortlist_dashboard_web_admin_integration_response(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    limit: int = 10,
    preview_limit: int = 400,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_dashboard_web_admin_integration_prompt(prompt)
    matched = matches_research_candidate_shortlist_dashboard_web_admin_integration_prompt(normalized_prompt)

    builder = _route_builder()
    response = _call_builder(
        builder,
        normalized_prompt,
        {
            "intake_dir": Path(intake_dir),
            "limit": limit,
            "preview_limit": preview_limit,
            "write_outputs": write_outputs,
            "json_requested": True,
        },
    )

    route_marker = response.get("route_marker") or response.get("marker")

    response["ok"] = bool(response.get("ok", True))
    response["matched"] = bool(response.get("matched", matched))
    response["integration_kind"] = INTEGRATION_KIND
    response["integration_marker"] = MARKER
    response["marker"] = MARKER
    response["route_marker"] = route_marker
    response["data_link_integration"] = DATA_LINK_INTEGRATION

    if "shortlist" not in response:
        response["shortlist"] = _find_records(response)

    _ensure_integration_html(response)

    if not json_requested:
        response.pop("json_text", None)

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_integration(*args: Any, **kwargs: Any) -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_integration_response(
            "show research archive candidate shortlist dashboard web admin integration",
            intake_dir=intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )

    html_text = str(response.get("html") or "")

    if not response.get("ok"):
        failures.append("integration response should be ok")
    if not response.get("matched"):
        failures.append("integration response should be matched")
    if response.get("integration_marker") != MARKER:
        failures.append("integration marker mismatch")
    if response.get("marker") != MARKER:
        failures.append("marker mismatch")
    if response.get("data_link_integration") != DATA_LINK_INTEGRATION:
        failures.append("data-link integration mismatch")
    if DATA_LINK_INTEGRATION not in html_text:
        failures.append("html missing data-link integration card")
    if "data-link-destructive=\"false\"" not in html_text:
        failures.append("html should be explicitly non-destructive")
    if "Research archive candidate shortlist" not in html_text:
        failures.append("html missing title")
    if "<table>" not in html_text:
        failures.append("html missing literal candidate table")
    if not response.get("shortlist"):
        failures.append("response should include shortlist candidates")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_integration()
    if failures:
        print("research archive candidate shortlist dashboard web admin integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="show research archive candidate shortlist dashboard web admin integration")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=400)
    parser.add_argument("--no-write-outputs", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    response = build_research_candidate_shortlist_dashboard_web_admin_integration_response(
        args.prompt,
        intake_dir=Path(args.intake_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=not args.no_write_outputs,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True, default=str))
        return

    print(response.get("html") or MARKER)


if __name__ == "__main__":
    main()
