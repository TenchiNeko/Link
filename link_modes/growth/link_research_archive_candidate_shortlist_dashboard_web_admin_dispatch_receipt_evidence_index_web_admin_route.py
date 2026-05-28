#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

import link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index as evidence_index
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route OK"
ROUTE_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route"
DATA_LINK_ROUTE = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-receipt-evidence-index-web-admin-route"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parents[2] / ".link_research_intake"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / ".link_research_evidence"


TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route",
    "research candidate shortlist dashboard dispatch receipt evidence index web admin route",
    "candidate shortlist dashboard dispatch receipt evidence index web admin route",
    "show research shortlist dashboard dispatch receipt evidence index web admin route",
    "view research shortlist dashboard dispatch receipt evidence index web admin route",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_prompt(
    prompt: str,
) -> str:
    return " ".join(str(prompt or "").strip().lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_prompt(
    prompt: str,
) -> bool:
    normalized = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_prompt(prompt)
    if not normalized:
        return False

    if normalized in TRIGGERS:
        return True

    required = (
        "research",
        "candidate",
        "shortlist",
        "dashboard",
        "web admin",
        "dispatch",
        "receipt",
        "evidence",
        "index",
        "route",
    )
    return all(token in normalized for token in required)


def _call_evidence_index_response(prompt: str, **kwargs: Any) -> dict[str, Any]:
    builder = evidence_index.build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_response
    signature = inspect.signature(builder)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }

    try:
        response = builder(prompt, **accepted)
    except TypeError:
        if "prompt" in signature.parameters:
            accepted["prompt"] = prompt
        response = builder(**accepted)

    if not isinstance(response, dict):
        return {
            "ok": False,
            "matched": False,
            "error": f"evidence index builder returned {type(response).__name__}",
        }

    return response


def _summary_json(response: dict[str, Any]) -> dict[str, Any]:
    html_text = str(response.get("html") or "")
    index_response = response.get("index_response") or {}
    return {
        "ok": bool(response.get("ok")),
        "matched": bool(response.get("matched")),
        "route_marker": response.get("route_marker"),
        "route_kind": response.get("route_kind"),
        "data_link_route": response.get("data_link_route"),
        "index_marker": response.get("index_marker"),
        "integration_marker": response.get("integration_marker"),
        "route_source_marker": response.get("route_source_marker"),
        "receipt_marker": response.get("receipt_marker"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
        "evidence_count": len(response.get("evidence_records") or []),
        "has_literal_table": "<table>" in html_text,
        "has_non_destructive": 'data-link-destructive="false"' in html_text,
        "output_paths": index_response.get("output_paths") or {},
    }


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_html(
    response: dict[str, Any],
) -> str:
    index_html = response.get("index_html") or ""
    output_paths = response.get("output_paths") or {}

    rows = ""
    for key, value in sorted(output_paths.items()):
        rows += (
            "<tr>"
            f"<td><code>{key}</code></td>"
            f"<td><code>{value}</code></td>"
            "</tr>"
        )

    if not rows:
        rows = "<tr><td><code>none</code></td><td><code></code></td></tr>"

    return (
        f'<section data-link-card="{DATA_LINK_ROUTE}" '
        f'data-link-route="{DATA_LINK_ROUTE}" '
        f'data-link-route-kind="{ROUTE_KIND}" '
        f'data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard dispatch receipt evidence index route</h2>"
        "<p>Routes the evidence index for the dashboard web-admin dispatch receipt chain.</p>"
        "<table>"
        "<thead><tr><th>Output</th><th>Path</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        f"{index_html}"
        "</section>"
    )


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_response(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    limit: int = 10,
    preview_limit: int = 5,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_prompt(prompt)

    index_response = _call_evidence_index_response(
        "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index",
        intake_dir=Path(intake_dir),
        output_dir=Path(output_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    response: dict[str, Any] = {
        "ok": bool(index_response.get("ok")) and matched,
        "matched": matched,
        "route_marker": MARKER,
        "route_kind": ROUTE_KIND,
        "data_link_route": DATA_LINK_ROUTE,
        "index_marker": index_response.get("index_marker"),
        "integration_marker": index_response.get("integration_marker"),
        "route_source_marker": index_response.get("route_marker"),
        "receipt_marker": index_response.get("receipt_marker"),
        "candidate_count": index_response.get("candidate_count"),
        "shortlist_count": index_response.get("shortlist_count"),
        "evidence_records": index_response.get("evidence_records") or [],
        "output_paths": dict(index_response.get("output_paths") or {}),
        "index_response": index_response,
        "index_html": index_response.get("html") or "",
    }

    response["html"] = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_html(response)

    if json_requested:
        response["json"] = _summary_json(response)

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        output_dir = Path(tmp) / "evidence"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_response(
            "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route",
            intake_dir=intake_dir,
            output_dir=output_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dispatch receipt evidence index web admin route response should be ok")
        if not response.get("matched"):
            failures.append("dispatch receipt evidence index web admin route response should be matched")
        if response.get("route_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin route marker mismatch")
        if response.get("route_kind") != ROUTE_KIND:
            failures.append("dispatch receipt evidence index web admin route kind mismatch")
        if response.get("data_link_route") != DATA_LINK_ROUTE:
            failures.append("dispatch receipt evidence index web admin route data-link mismatch")

        html_text = response.get("html") or ""
        if DATA_LINK_ROUTE not in html_text:
            failures.append("dispatch receipt evidence index web admin route html missing data-link route")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dispatch receipt evidence index web admin route html should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dispatch receipt evidence index web admin route html missing literal table")

        if response.get("index_marker") != evidence_index.MARKER:
            failures.append("dispatch receipt evidence index web admin route missing LU64 marker")

        records = response.get("evidence_records") or []
        if not records:
            failures.append("dispatch receipt evidence index web admin route should include evidence records")

        output_paths = response.get("output_paths") or {}
        for key in ("receipt_json", "receipt_report", "evidence_index_json", "evidence_index_report"):
            value = output_paths.get(key)
            if not value:
                failures.append(f"dispatch receipt evidence index web admin route missing output path: {key}")
            elif not Path(value).exists():
                failures.append(f"dispatch receipt evidence index web admin route output path does not exist: {key}")

        payload = response.get("json") or {}
        if payload.get("route_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin route JSON marker mismatch")
        if not payload.get("has_literal_table"):
            failures.append("dispatch receipt evidence index web admin route JSON should confirm literal table")
        if not payload.get("has_non_destructive"):
            failures.append("dispatch receipt evidence index web admin route JSON should confirm non-destructive")
        if payload.get("evidence_count", 0) < 1:
            failures.append("dispatch receipt evidence index web admin route JSON should include evidence count")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route"
    )
    parser.add_argument("prompt", nargs="?", default="show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin route")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-outputs", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_route_response(
        args.prompt,
        intake_dir=Path(args.intake_dir),
        output_dir=Path(args.output_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=not args.no_write_outputs,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response.get("json") or _summary_json(response), indent=2, sort_keys=True))
    else:
        print(response["html"])


if __name__ == "__main__":
    main()
