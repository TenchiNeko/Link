#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

import link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_integration as integration
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch OK"
DISPATCH_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch"
DATA_LINK_DISPATCH = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-receipt-evidence-index-web-admin-dispatch"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parent / ".link_research_intake"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / ".link_research_evidence"


TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch",
    "research candidate shortlist dashboard dispatch receipt evidence index web admin dispatch",
    "candidate shortlist dashboard dispatch receipt evidence index web admin dispatch",
    "show research shortlist dashboard dispatch receipt evidence index web admin dispatch",
    "view research shortlist dashboard dispatch receipt evidence index web admin dispatch",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_prompt(
    prompt: str,
) -> str:
    return " ".join(str(prompt or "").strip().lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_prompt(
    prompt: str,
) -> bool:
    normalized = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_prompt(prompt)
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
    )
    return all(token in normalized for token in required) and "dispatch" in normalized


def _call_integration_response(prompt: str, **kwargs: Any) -> dict[str, Any]:
    builder = integration.build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_integration_response
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
            "error": f"integration builder returned {type(response).__name__}",
        }

    return response


def dispatch_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    limit: int = 10,
    preview_limit: int = 5,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    return build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_response(
        prompt,
        intake_dir=intake_dir,
        output_dir=output_dir,
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=json_requested,
    )


def _summary_json(response: dict[str, Any]) -> dict[str, Any]:
    html_text = str(response.get("html") or "")
    integration_response = response.get("integration_response") or {}

    return {
        "ok": bool(response.get("ok")),
        "matched": bool(response.get("matched")),
        "dispatch_marker": response.get("dispatch_marker"),
        "dispatch_kind": response.get("dispatch_kind"),
        "data_link_dispatch": response.get("data_link_dispatch"),
        "integration_marker": response.get("integration_marker"),
        "integration_kind": response.get("integration_kind"),
        "route_marker": response.get("route_marker"),
        "route_kind": response.get("route_kind"),
        "index_marker": response.get("index_marker"),
        "route_source_marker": response.get("route_source_marker"),
        "receipt_marker": response.get("receipt_marker"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
        "evidence_count": len(response.get("evidence_records") or []),
        "has_literal_table": "<table>" in html_text,
        "has_non_destructive": 'data-link-destructive="false"' in html_text,
        "output_paths": integration_response.get("output_paths") or {},
    }


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_html(
    response: dict[str, Any],
) -> str:
    integration_html = response.get("integration_html") or ""
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
        f'<section data-link-card="{DATA_LINK_DISPATCH}" '
        f'data-link-dispatch="{DATA_LINK_DISPATCH}" '
        f'data-link-dispatch-kind="{DISPATCH_KIND}" '
        f'data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard dispatch receipt evidence index web-admin dispatch</h2>"
        "<p>Dispatches the LU66 web-admin integration response for the dispatch receipt evidence index chain.</p>"
        "<table>"
        "<thead><tr><th>Output</th><th>Path</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        f"{integration_html}"
        "</section>"
    )


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_response(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    limit: int = 10,
    preview_limit: int = 5,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_prompt(prompt)

    integration_response = _call_integration_response(
        "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin integration",
        intake_dir=Path(intake_dir),
        output_dir=Path(output_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    response: dict[str, Any] = {
        "ok": bool(integration_response.get("ok")) and matched,
        "matched": matched,
        "dispatch_marker": MARKER,
        "dispatch_kind": DISPATCH_KIND,
        "data_link_dispatch": DATA_LINK_DISPATCH,
        "integration_marker": integration_response.get("integration_marker"),
        "integration_kind": integration_response.get("integration_kind"),
        "route_marker": integration_response.get("route_marker"),
        "route_kind": integration_response.get("route_kind"),
        "index_marker": integration_response.get("index_marker"),
        "route_source_marker": integration_response.get("route_source_marker"),
        "receipt_marker": integration_response.get("receipt_marker"),
        "candidate_count": integration_response.get("candidate_count"),
        "shortlist_count": integration_response.get("shortlist_count"),
        "evidence_records": integration_response.get("evidence_records") or [],
        "output_paths": dict(integration_response.get("output_paths") or {}),
        "integration_response": integration_response,
        "integration_html": integration_response.get("html") or "",
    }

    response["html"] = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_html(response)

    if json_requested:
        response["json"] = _summary_json(response)

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        output_dir = Path(tmp) / "evidence"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_response(
            "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch",
            intake_dir=intake_dir,
            output_dir=output_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dispatch receipt evidence index web admin dispatch response should be ok")
        if not response.get("matched"):
            failures.append("dispatch receipt evidence index web admin dispatch response should be matched")
        if response.get("dispatch_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch marker mismatch")
        if response.get("dispatch_kind") != DISPATCH_KIND:
            failures.append("dispatch receipt evidence index web admin dispatch kind mismatch")
        if response.get("data_link_dispatch") != DATA_LINK_DISPATCH:
            failures.append("dispatch receipt evidence index web admin dispatch data-link mismatch")

        html_text = response.get("html") or ""
        if DATA_LINK_DISPATCH not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch html missing data-link dispatch")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch html should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch html missing literal table")

        if response.get("integration_marker") != integration.MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch missing LU66 integration marker")

        records = response.get("evidence_records") or []
        if not records:
            failures.append("dispatch receipt evidence index web admin dispatch should include evidence records")

        output_paths = response.get("output_paths") or {}
        for key in ("receipt_json", "receipt_report", "evidence_index_json", "evidence_index_report"):
            value = output_paths.get(key)
            if not value:
                failures.append(f"dispatch receipt evidence index web admin dispatch missing output path: {key}")
            elif not Path(value).exists():
                failures.append(f"dispatch receipt evidence index web admin dispatch output path does not exist: {key}")

        payload = response.get("json") or {}
        if payload.get("dispatch_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch JSON marker mismatch")
        if not payload.get("has_literal_table"):
            failures.append("dispatch receipt evidence index web admin dispatch JSON should confirm literal table")
        if not payload.get("has_non_destructive"):
            failures.append("dispatch receipt evidence index web admin dispatch JSON should confirm non-destructive")
        if payload.get("evidence_count", 0) < 1:
            failures.append("dispatch receipt evidence index web admin dispatch JSON should include evidence count")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch"
    )
    parser.add_argument("prompt", nargs="?", default="show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch")
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

    response = dispatch_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin(
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
