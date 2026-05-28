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


UPSTREAM_MODULE = "link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_web_admin_integration"
integ = importlib.import_module(UPSTREAM_MODULE)


MARKER = "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index OK"
INDEX_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index"
DATA_LINK_INDEX = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-receipt-evidence-index-web-admin-dispatch-receipt-evidence-index-web-admin-dispatch-receipt-evidence-index"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parents[2] / ".link_research_intake"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / ".link_research_evidence"


TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index",
    "research candidate shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt evidence index",
    "candidate shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt evidence index",
    "show research shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt evidence index",
    "view research shortlist dashboard dispatch receipt evidence index web admin dispatch receipt evidence index dispatch receipt evidence index",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_prompt(
    prompt: str,
) -> str:
    return " ".join(str(prompt or "").strip().lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_prompt(
    prompt: str,
) -> bool:
    normalized = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_prompt(prompt)
    if not normalized:
        return False

    if normalized in TRIGGERS:
        return True

    required = (
        "research",
        "candidate",
        "shortlist",
        "dashboard",
        "dispatch",
        "receipt",
        "evidence",
        "index",
    )
    return all(token in normalized for token in required) and normalized.count("receipt") >= 2 and normalized.count("index") >= 2


def _call_integration_response(prompt: str, **kwargs: Any) -> dict[str, Any]:
    builder = integ.build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_web_admin_integration_response
    response = builder(prompt, **kwargs)

    if not isinstance(response, dict):
        return {
            "ok": False,
            "matched": False,
            "error": f"integration builder returned {type(response).__name__}",
        }

    return response


def _evidence_records(response: dict[str, Any]) -> list[dict[str, Any]]:
    records = list(response.get("upstream_evidence_records") or [])

    own_record = {
        "kind": INDEX_KIND,
        "marker": MARKER,
        "data_link": DATA_LINK_INDEX,
        "generated_at": response.get("generated_at"),
        "source_integration_kind": response.get("integration_kind"),
        "source_integration_marker": response.get("integration_marker"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
    }

    if not any(record.get("marker") == MARKER for record in records):
        records.append(own_record)

    return records


def _write_evidence_outputs(response: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "ok": response.get("ok"),
        "matched": response.get("matched"),
        "index_marker": response.get("index_marker"),
        "index_kind": response.get("index_kind"),
        "data_link_index": response.get("data_link_index"),
        "integration_marker": response.get("integration_marker"),
        "integration_kind": response.get("integration_kind"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
        "evidence_records": response.get("evidence_records") or [],
        "generated_at": response.get("generated_at"),
        "output_paths": response.get("output_paths") or {},
    }

    json_path = output_dir / "research_candidate_shortlist_dashboard_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index.json"
    report_path = output_dir / "research_candidate_shortlist_dashboard_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index.md"

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    rows = [
        "# Research candidate shortlist dashboard dispatch receipt evidence index",
        "",
        f"- Marker: `{response.get('index_marker')}`",
        f"- Kind: `{response.get('index_kind')}`",
        f"- Data link: `{response.get('data_link_index')}`",
        f"- Integration marker: `{response.get('integration_marker')}`",
        f"- Candidate count: `{response.get('candidate_count')}`",
        f"- Shortlist count: `{response.get('shortlist_count')}`",
        f"- Evidence count: `{len(response.get('evidence_records') or [])}`",
        "",
        "## Evidence records",
        "",
    ]

    for record in response.get("evidence_records") or []:
        rows.append(f"- `{record.get('kind')}` — `{record.get('marker')}`")

    report_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    output_paths = dict(response.get("output_paths") or {})
    output_paths["evidence_index_json"] = str(json_path)
    output_paths["evidence_index_report"] = str(report_path)
    return output_paths


def _summary_json(response: dict[str, Any]) -> dict[str, Any]:
    html_text = str(response.get("html") or "")

    return {
        "ok": bool(response.get("ok")),
        "matched": bool(response.get("matched")),
        "index_marker": response.get("index_marker"),
        "index_kind": response.get("index_kind"),
        "data_link_index": response.get("data_link_index"),
        "integration_marker": response.get("integration_marker"),
        "integration_kind": response.get("integration_kind"),
        "data_link_integration": response.get("data_link_integration"),
        "route_marker": response.get("route_marker"),
        "route_kind": response.get("route_kind"),
        "receipt_marker": response.get("receipt_marker"),
        "receipt_kind": response.get("receipt_kind"),
        "dispatch_marker": response.get("dispatch_marker"),
        "dispatch_kind": response.get("dispatch_kind"),
        "prior_index_marker": response.get("prior_index_marker"),
        "prior_index_kind": response.get("prior_index_kind"),
        "prior_receipt_marker": response.get("prior_receipt_marker"),
        "prior_receipt_kind": response.get("prior_receipt_kind"),
        "source_integration_marker": response.get("source_integration_marker"),
        "source_integration_kind": response.get("source_integration_kind"),
        "candidate_count": response.get("candidate_count"),
        "shortlist_count": response.get("shortlist_count"),
        "evidence_count": len(response.get("evidence_records") or []),
        "has_literal_table": "<table>" in html_text,
        "has_non_destructive": 'data-link-destructive="false"' in html_text,
        "output_paths": response.get("output_paths") or {},
    }


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_html(
    response: dict[str, Any],
) -> str:
    integration_html = response.get("integration_html") or ""
    output_paths = response.get("output_paths") or {}
    records = response.get("evidence_records") or []

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
        f'<section data-link-card="{DATA_LINK_INDEX}" '
        f'data-link-index="{DATA_LINK_INDEX}" '
        f'data-link-index-kind="{INDEX_KIND}" '
        f'data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard dispatch receipt evidence index web-admin dispatch receipt evidence index web-admin dispatch receipt evidence index</h2>"
        "<p>Read-only evidence index over the LU79 dispatch receipt web-admin integration.</p>"
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


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_response(
    prompt: str,
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    limit: int = 10,
    preview_limit: int = 5,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_prompt(prompt)

    integration_response = _call_integration_response(
        "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt web admin integration",
        intake_dir=Path(intake_dir),
        output_dir=Path(output_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    generated_at = datetime.now(timezone.utc).isoformat()

    response: dict[str, Any] = {
        "ok": bool(integration_response.get("ok")) and matched,
        "matched": matched,
        "index_marker": MARKER,
        "index_kind": INDEX_KIND,
        "data_link_index": DATA_LINK_INDEX,
        "integration_marker": integration_response.get("integration_marker"),
        "integration_kind": integration_response.get("integration_kind"),
        "data_link_integration": integration_response.get("data_link_integration"),
        "route_marker": integration_response.get("route_marker"),
        "route_kind": integration_response.get("route_kind"),
        "receipt_marker": integration_response.get("receipt_marker"),
        "receipt_kind": integration_response.get("receipt_kind"),
        "dispatch_marker": integration_response.get("dispatch_marker"),
        "dispatch_kind": integration_response.get("dispatch_kind"),
        "prior_index_marker": integration_response.get("index_marker"),
        "prior_index_kind": integration_response.get("index_kind"),
        "prior_receipt_marker": integration_response.get("prior_receipt_marker"),
        "prior_receipt_kind": integration_response.get("prior_receipt_kind"),
        "source_integration_marker": integration_response.get("source_integration_marker"),
        "source_integration_kind": integration_response.get("source_integration_kind"),
        "candidate_count": integration_response.get("candidate_count"),
        "shortlist_count": integration_response.get("shortlist_count"),
        "output_paths": dict(integration_response.get("output_paths") or {}),
        "upstream_evidence_records": list(integration_response.get("evidence_records") or []),
        "integration_response": integration_response,
        "integration_html": integration_response.get("html") or "",
        "generated_at": generated_at,
    }

    response["evidence_records"] = _evidence_records(response)

    if write_outputs:
        response["output_paths"] = _write_evidence_outputs(response, Path(output_dir))

    response["html"] = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_html(response)

    if json_requested:
        response["json"] = _summary_json(response)

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        output_dir = Path(tmp) / "evidence"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_response(
            "show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index",
            intake_dir=intake_dir,
            output_dir=output_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index response should be ok")
        if not response.get("matched"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index response should be matched")
        if response.get("index_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index marker mismatch")
        if response.get("index_kind") != INDEX_KIND:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index kind mismatch")
        if response.get("data_link_index") != DATA_LINK_INDEX:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index data-link mismatch")
        if response.get("integration_marker") != integ.MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index missing LU79 integration marker")

        html_text = response.get("html") or ""
        if DATA_LINK_INDEX not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index html missing data-link index")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index html should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index html missing literal table")

        output_paths = response.get("output_paths") or {}
        for key in ("evidence_index_json", "evidence_index_report"):
            value = output_paths.get(key)
            if not value:
                failures.append(f"dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index missing output path: {key}")
            elif not Path(value).exists():
                failures.append(f"dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index output path does not exist: {key}")

        records = response.get("evidence_records") or []
        if not records:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index should include evidence records")
        if not any(record.get("marker") == MARKER for record in records):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index should include own evidence record")

        payload = response.get("json") or {}
        if payload.get("index_marker") != MARKER:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index JSON marker mismatch")
        if not payload.get("has_literal_table"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index JSON should confirm literal table")
        if not payload.get("has_non_destructive"):
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index JSON should confirm non-destructive")
        if payload.get("evidence_count", 0) < 1:
            failures.append("dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index JSON should include evidence count")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index"
    )
    parser.add_argument("prompt", nargs="?", default="show research archive candidate shortlist dashboard web admin dispatch receipt evidence index web admin dispatch receipt evidence index web admin dispatch receipt evidence index")
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

    response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_web_admin_dispatch_receipt_evidence_index_response(
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
