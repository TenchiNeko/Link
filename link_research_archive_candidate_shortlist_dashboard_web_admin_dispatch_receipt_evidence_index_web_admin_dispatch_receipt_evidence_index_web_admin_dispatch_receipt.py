#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


UPSTREAM_MODULE = "link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_integration"
integ = importlib.import_module(UPSTREAM_MODULE)


MARKER = "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt OK"
RECEIPT_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt"
DATA_LINK_RECEIPT = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-receipt-evidence-index-web-admin-dispatch-receipt-evidence-index-web-admin-dispatch-receipt"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parent / ".link_research_intake"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / ".link_research_evidence"


TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt",
    "research candidate shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt",
    "candidate shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt",
    "show research shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt",
    "view research shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_prompt(
    prompt: str,
) -> str:
    return " ".join(str(prompt or "").strip().lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_prompt(
    prompt: str,
) -> bool:
    normalized = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_prompt(prompt)
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
    return all(token in normalized for token in required) and normalized.count("receipt") >= 2


def _call_integration_response(prompt: str, **kwargs: Any) -> dict[str, Any]:
    builder = integ.build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_integration_response
    response = builder(prompt, **kwargs)

    if not isinstance(response, dict):
        return {
            "ok": False,
            "matched": False,
            "error": f"integration builder returned {type(response).__name__}",
        }

    return response


def _summary_json(response: dict[str, Any]) -> dict[str, Any]:
    html_text = str(response.get("html") or "")

    return {
        "ok": bool(response.get("ok")),
        "matched": bool(response.get("matched")),
        "receipt_marker": response.get("receipt_marker"),
        "receipt_kind": response.get("receipt_kind"),
        "data_link_receipt": response.get("data_link_receipt"),
        "source_integration_marker": response.get("source_integration_marker"),
        "source_integration_kind": response.get("source_integration_kind"),
        "dispatch_marker": response.get("dispatch_marker"),
        "dispatch_kind": response.get("dispatch_kind"),
        "route_marker": response.get("route_marker"),
        "route_kind": response.get("route_kind"),
        "index_marker": response.get("index_marker"),
        "index_kind": response.get("index_kind"),
        "prior_receipt_marker": response.get("prior_receipt_marker"),
        "prior_receipt_kind": response.get("prior_receipt_kind"),
        "upstream_integration_marker": response.get("upstream_integration_marker"),
        "upstream_integration_kind": response.get("upstream_integration_kind"),
        "source_receipt_marker": response.get("source_receipt_marker"),
        "source_index_marker": response.get("source_index_marker"),
        "index_route_marker": response.get("index_route_marker"),
        "route_source_marker": response.get("route_source_marker"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
        "evidence_count": len(response.get("evidence_records") or []),
        "has_literal_table": "<table>" in html_text,
        "has_non_destructive": 'data-link-destructive="false"' in html_text,
        "output_paths": response.get("output_paths") or {},
    }


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_html(
    response: dict[str, Any],
) -> str:
    integration_html = response.get("integration_html") or ""
    output_paths = response.get("output_paths") or {}
    records = response.get("evidence_records") or []
    generated_at = response.get("generated_at") or ""

    path_rows = ""
    for key, value in sorted(output_paths.items()):
        path_rows += (
            "<tr>"
            f"<td><code>{key}</code></td>"
            f"<td><code>{value}</code></td>"
            "</tr>"
        )

    if not path_rows:
        path_rows = "<tr><td><code>none</code></td><td><code></code></td></tr>"

    evidence_rows = ""
    for record in records:
        evidence_rows += (
            "<tr>"
            f"<td><code>{record.get('kind') or ''}</code></td>"
            f"<td><code>{record.get('marker') or ''}</code></td>"
            f"<td><code>{record.get('data_link') or ''}</code></td>"
            "</tr>"
        )

    if not evidence_rows:
        evidence_rows = "<tr><td><code>none</code></td><td><code></code></td><td><code></code></td></tr>"

    return (
        f'<section data-link-card="{DATA_LINK_RECEIPT}" '
        f'data-link-receipt="{DATA_LINK_RECEIPT}" '
        f'data-link-receipt-kind="{RECEIPT_KIND}" '
        f'data-link-generated-at="{generated_at}" '
        f'data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard dispatch receipt evidence index web-admin dispatch receipt evidence index web-admin dispatch receipt</h2>"
        "<p>Read-only receipt wrapper for the LU76 web-admin dispatch integration.</p>"
        "<table>"
        "<thead><tr><th>Output</th><th>Path</th></tr></thead>"
        f"<tbody>{path_rows}</tbody>"
        "</table>"
        "<table>"
        "<thead><tr><th>Kind</th><th>Marker</th><th>Data link</th></tr></thead>"
        f"<tbody>{evidence_rows}</tbody>"
        "</table>"
        f"{integration_html}"
        "</section>"
    )


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_response(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    limit: int = 10,
    preview_limit: int = 5,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_prompt(prompt)

    integration_response = _call_integration_response(
        "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch integration",
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "receipt_marker": MARKER,
        "receipt_kind": RECEIPT_KIND,
        "data_link_receipt": DATA_LINK_RECEIPT,
        "source_integration_marker": integration_response.get("integration_marker"),
        "source_integration_kind": integration_response.get("integration_kind"),
        "dispatch_marker": integration_response.get("dispatch_marker"),
        "dispatch_kind": integration_response.get("dispatch_kind"),
        "route_marker": integration_response.get("route_marker"),
        "route_kind": integration_response.get("route_kind"),
        "index_marker": integration_response.get("index_marker"),
        "index_kind": integration_response.get("index_kind"),
        "prior_receipt_marker": integration_response.get("receipt_marker"),
        "prior_receipt_kind": integration_response.get("receipt_kind"),
        "upstream_integration_marker": integration_response.get("upstream_integration_marker"),
        "upstream_integration_kind": integration_response.get("upstream_integration_kind"),
        "source_receipt_marker": integration_response.get("source_receipt_marker"),
        "source_index_marker": integration_response.get("source_index_marker"),
        "index_route_marker": integration_response.get("index_route_marker"),
        "route_source_marker": integration_response.get("route_source_marker"),
        "candidate_count": integration_response.get("candidate_count"),
        "shortlist_count": integration_response.get("shortlist_count"),
        "output_paths": dict(integration_response.get("output_paths") or {}),
        "evidence_records": list(integration_response.get("evidence_records") or []),
        "integration_response": integration_response,
        "integration_html": integration_response.get("html") or "",
    }

    response["html"] = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_html(response)

    if json_requested:
        response["json"] = _summary_json(response)

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        output_dir = Path(tmp) / "evidence"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_response(
            "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt",
            intake_dir=intake_dir,
            output_dir=output_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt response should be ok")
        if not response.get("matched"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt response should be matched")
        if response.get("receipt_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt marker mismatch")
        if response.get("receipt_kind") != RECEIPT_KIND:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt kind mismatch")
        if response.get("data_link_receipt") != DATA_LINK_RECEIPT:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt data-link mismatch")
        if response.get("source_integration_marker") != integ.MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt missing LU76 integration marker")

        html_text = response.get("html") or ""
        if DATA_LINK_RECEIPT not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt html missing data-link receipt")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt html should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt html missing literal table")

        output_paths = response.get("output_paths") or {}
        for key in ("evidence_index_json", "evidence_index_report"):
            value = output_paths.get(key)
            if not value:
                failures.append(f"dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt missing inherited output path: {key}")
            elif not Path(value).exists():
                failures.append(f"dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt output path does not exist: {key}")

        records = response.get("evidence_records") or []
        if not records:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt should inherit evidence records")

        payload = response.get("json") or {}
        if payload.get("receipt_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt JSON marker mismatch")
        if not payload.get("has_literal_table"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt JSON should confirm literal table")
        if not payload.get("has_non_destructive"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt JSON should confirm non-destructive")
        if payload.get("evidence_count", 0) < 1:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt JSON should include evidence count")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt"
    )
    parser.add_argument("prompt", nargs="?", default="show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt")
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

    response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_response(
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
