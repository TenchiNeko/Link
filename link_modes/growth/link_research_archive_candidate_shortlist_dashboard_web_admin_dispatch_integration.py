#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch as dispatch
from .link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin dispatch integration OK"
INTEGRATION_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration"
DATA_LINK_INTEGRATION = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-integration"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parents[2] / ".link_research_intake"

TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch integration",
    "research candidate shortlist dashboard web admin dispatch integration",
    "candidate shortlist dashboard web admin dispatch integration",
    "research archive candidate shortlist dashboard dispatch integration",
    "show research shortlist dashboard web admin dispatch integration",
    "view research shortlist dashboard web admin dispatch integration",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_prompt(prompt: str) -> str:
    return " ".join((prompt or "").lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_prompt(prompt: str) -> bool:
    lowered = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_prompt(prompt)
    return any(trigger in lowered for trigger in TRIGGERS) or (
        "research" in lowered
        and "candidate" in lowered
        and "shortlist" in lowered
        and "dashboard" in lowered
        and "web admin" in lowered
        and "dispatch" in lowered
        and "integration" in lowered
    )


def _get_dispatch_builder() -> Callable[..., dict[str, Any]]:
    preferred = "build_research_candidate_shortlist_dashboard_web_admin_dispatch_response"
    builder = getattr(dispatch, preferred, None)
    if callable(builder):
        return builder

    for name in dir(dispatch):
        value = getattr(dispatch, name)
        if (
            callable(value)
            and name.startswith("build_")
            and "candidate_shortlist" in name
            and "dashboard" in name
            and "dispatch" in name
        ):
            return value

    raise RuntimeError("Could not find LU59 dispatch response builder")


def _call_dispatch_response(
    prompt: str,
    *,
    intake_dir: Path,
    limit: int,
    preview_limit: int,
    write_outputs: bool,
    json_requested: bool,
) -> dict[str, Any]:
    builder = _get_dispatch_builder()
    kwargs: dict[str, Any] = {
        "intake_dir": Path(intake_dir),
        "limit": limit,
        "preview_limit": preview_limit,
        "write_outputs": write_outputs,
        "json_requested": json_requested,
    }

    signature = inspect.signature(builder)
    accepted = {key: value for key, value in kwargs.items() if key in signature.parameters}

    try:
        response = builder(prompt, **accepted)
    except TypeError:
        response = builder(**accepted)

    if not isinstance(response, dict):
        raise TypeError("LU59 dispatch response builder did not return a dict")

    return response


def _find_candidate_records(payload: dict[str, Any]) -> list[Any]:
    keys = (
        "shortlist",
        "records",
        "candidates",
        "top_candidates",
        "candidate_shortlist",
    )

    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    nested_keys = (
        "response",
        "route_response",
        "integration_response",
        "dispatch_response",
        "web_admin_response",
        "dashboard_response",
        "exporter_response",
        "data",
    )

    for key in nested_keys:
        value = payload.get(key)
        if isinstance(value, dict):
            found = _find_candidate_records(value)
            if found:
                return found

    return []


def _field(record: Any, *names: str) -> str:
    if not isinstance(record, dict):
        return str(record)
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _minimal_candidate_table(payload: dict[str, Any]) -> str:
    records = _find_candidate_records(payload)
    if not records:
        return "<table><tr><th>Candidate</th><th>Score</th><th>Summary</th></tr></table>"

    rows = []
    for index, record in enumerate(records[:10], 1):
        candidate = _field(record, "candidate", "path", "file", "source", "name") or f"candidate-{index}"
        score = _field(record, "score", "rank_score", "confidence", "priority")
        summary = _field(record, "summary", "reason", "rationale", "title")
        rows.append(
            "<tr>"
            f"<td><code>{candidate}</code></td>"
            f"<td>{score}</td>"
            f"<td>{summary}</td>"
            "</tr>"
        )

    return "<table><tr><th>Candidate</th><th>Score</th><th>Summary</th></tr>" + "".join(rows) + "</table>"


def _augment_html(response: dict[str, Any]) -> str:
    existing = str(response.get("html") or "")
    if "<table>" not in existing:
        existing += _minimal_candidate_table(response)

    return (
        f'<section data-link-card="{DATA_LINK_INTEGRATION}" '
        f'data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard web admin dispatch integration</h2>"
        f"{existing}"
        "</section>"
    )


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_response(
    prompt: str = "research archive candidate shortlist dashboard web admin dispatch integration",
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    limit: int = 10,
    preview_limit: int = 3,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_prompt(prompt)
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_prompt(normalized_prompt)

    dispatch_response = _call_dispatch_response(
        normalized_prompt,
        intake_dir=Path(intake_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    response = dict(dispatch_response)
    response["ok"] = bool(dispatch_response.get("ok", True))
    response["matched"] = matched or bool(dispatch_response.get("matched"))
    response["marker"] = MARKER
    response["integration_marker"] = MARKER
    response["integration_kind"] = INTEGRATION_KIND
    response["data_link_integration"] = DATA_LINK_INTEGRATION
    response["dispatch_response"] = dispatch_response

    if "shortlist_count" not in response:
        response["shortlist_count"] = len(_find_candidate_records(response))

    response["html"] = _augment_html(response)

    if json_requested:
        response["json"] = {
            "ok": response.get("ok"),
            "matched": response.get("matched"),
            "integration_marker": MARKER,
            "data_link_integration": DATA_LINK_INTEGRATION,
            "candidate_count": response.get("candidate_count"),
            "shortlist_count": response.get("shortlist_count"),
            "has_literal_table": "<table>" in response.get("html", ""),
            "has_non_destructive": 'data-link-destructive="false"' in response.get("html", ""),
        }

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_integration() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_response(
            "show research archive candidate shortlist dashboard web admin dispatch integration",
            intake_dir=intake_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

    if not response.get("ok"):
        failures.append("dispatch integration response should be ok")
    if not response.get("matched"):
        failures.append("dispatch integration response should be matched")
    if response.get("integration_marker") != MARKER:
        failures.append("dispatch integration marker mismatch")
    if response.get("integration_kind") != INTEGRATION_KIND:
        failures.append("dispatch integration kind mismatch")
    if response.get("data_link_integration") != DATA_LINK_INTEGRATION:
        failures.append("dispatch integration data-link mismatch")

    html_text = response.get("html") or ""
    if DATA_LINK_INTEGRATION not in html_text:
        failures.append("dispatch integration html missing data-link integration")
    if 'data-link-destructive="false"' not in html_text:
        failures.append("dispatch integration html should be explicitly non-destructive")
    if "<table>" not in html_text:
        failures.append("dispatch integration html missing candidate table")
    if response.get("shortlist_count", 0) < 1:
        failures.append("dispatch integration should include shortlist candidates")

    payload = response.get("json") or {}
    if payload.get("integration_marker") != MARKER:
        failures.append("dispatch integration JSON marker mismatch")
    if not payload.get("has_literal_table"):
        failures.append("dispatch integration JSON should confirm literal table")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_integration()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="research archive candidate shortlist dashboard web admin dispatch integration")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE_DIR)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-write-outputs", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_response(
        args.prompt,
        intake_dir=args.intake_dir,
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=not args.no_write_outputs,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response.get("json", response), indent=2, sort_keys=True))
    else:
        print(response.get("html") or response.get("integration_marker") or MARKER)


if __name__ == "__main__":
    main()
