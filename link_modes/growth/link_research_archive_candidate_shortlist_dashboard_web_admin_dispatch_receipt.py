#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration as integration
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist dashboard web admin dispatch receipt OK"
RECEIPT_KIND = "research_archive_candidate_shortlist_dashboard_web_admin_dispatch_receipt"
DATA_LINK_RECEIPT = "research-archive-candidate-shortlist-dashboard-web-admin-dispatch-receipt"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parents[2] / ".link_research_intake"

TRIGGERS = (
    "research archive candidate shortlist dashboard web admin dispatch receipt",
    "research candidate shortlist dashboard web admin dispatch receipt",
    "candidate shortlist dashboard web admin dispatch receipt",
    "research archive candidate shortlist dispatch receipt",
    "show research shortlist dashboard web admin dispatch receipt",
    "view research shortlist dashboard web admin dispatch receipt",
)


def normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_prompt(prompt: str) -> str:
    return " ".join((prompt or "").lower().split())


def matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_prompt(prompt: str) -> bool:
    lowered = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_prompt(prompt)
    return any(trigger in lowered for trigger in TRIGGERS) or (
        "research" in lowered
        and "candidate" in lowered
        and "shortlist" in lowered
        and "dashboard" in lowered
        and "web admin" in lowered
        and "dispatch" in lowered
        and "receipt" in lowered
    )


def _get_integration_builder() -> Callable[..., dict[str, Any]]:
    preferred = "build_research_candidate_shortlist_dashboard_web_admin_dispatch_integration_response"
    builder = getattr(integration, preferred, None)
    if callable(builder):
        return builder

    for name in dir(integration):
        value = getattr(integration, name)
        if (
            callable(value)
            and name.startswith("build_")
            and "candidate_shortlist" in name
            and "dashboard" in name
            and "dispatch" in name
            and "integration" in name
        ):
            return value

    raise RuntimeError("Could not find LU60 dispatch integration response builder")


def _call_integration_response(
    prompt: str,
    *,
    intake_dir: Path,
    limit: int,
    preview_limit: int,
    write_outputs: bool,
    json_requested: bool,
) -> dict[str, Any]:
    builder = _get_integration_builder()
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
        raise TypeError("LU60 dispatch integration response builder did not return a dict")

    return response


def _find_candidate_records(payload: dict[str, Any]) -> list[Any]:
    for key in ("shortlist", "records", "candidates", "top_candidates", "candidate_shortlist"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for key in (
        "response",
        "route_response",
        "integration_response",
        "dispatch_response",
        "web_admin_response",
        "dashboard_response",
        "exporter_response",
        "data",
    ):
        value = payload.get(key)
        if isinstance(value, dict):
            found = _find_candidate_records(value)
            if found:
                return found

    return []


def _receipt_paths(intake_dir: Path) -> dict[str, Path]:
    receipt_dir = Path(intake_dir) / "receipts"
    return {
        "receipt_json": receipt_dir / "research_candidate_shortlist_dashboard_web_admin_dispatch_receipt.json",
        "receipt_report": receipt_dir / "research_candidate_shortlist_dashboard_web_admin_dispatch_receipt.md",
    }


def _write_receipt_outputs(receipt: dict[str, Any], intake_dir: Path) -> dict[str, str]:
    paths = _receipt_paths(intake_dir)
    paths["receipt_json"].parent.mkdir(parents=True, exist_ok=True)

    paths["receipt_json"].write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = [
        "# Research archive candidate shortlist dashboard web admin dispatch receipt",
        "",
        f"- ok: `{receipt.get('ok')}`",
        f"- matched: `{receipt.get('matched')}`",
        f"- receipt kind: `{receipt.get('receipt_kind')}`",
        f"- marker: `{receipt.get('receipt_marker')}`",
        f"- candidate count: `{receipt.get('candidate_count')}`",
        f"- shortlist count: `{receipt.get('shortlist_count')}`",
        f"- generated at: `{receipt.get('generated_at')}`",
        "",
    ]

    paths["receipt_report"].write_text("\n".join(report), encoding="utf-8")

    return {key: str(value) for key, value in paths.items()}


def _build_receipt_payload(
    integration_response: dict[str, Any],
    *,
    matched: bool,
    prompt: str,
) -> dict[str, Any]:
    records = _find_candidate_records(integration_response)

    return {
        "ok": bool(integration_response.get("ok", True)),
        "matched": matched or bool(integration_response.get("matched")),
        "receipt_marker": MARKER,
        "marker": MARKER,
        "receipt_kind": RECEIPT_KIND,
        "data_link_receipt": DATA_LINK_RECEIPT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "candidate_count": integration_response.get("candidate_count"),
        "shortlist_count": integration_response.get("shortlist_count", len(records)),
        "source_marker": integration_response.get("integration_marker") or integration_response.get("marker"),
        "source_kind": integration_response.get("integration_kind"),
        "source_data_link": integration_response.get("data_link_integration"),
        "has_literal_table": "<table>" in str(integration_response.get("html") or ""),
        "has_non_destructive": 'data-link-destructive="false"' in str(integration_response.get("html") or ""),
        "integration_response": integration_response,
    }


def _receipt_html(receipt: dict[str, Any]) -> str:
    return (
        f'<section data-link-card="{DATA_LINK_RECEIPT}" data-link-destructive="false">'
        "<h2>Research archive candidate shortlist dashboard web admin dispatch receipt</h2>"
        f"<p>Status: <strong>{receipt.get('ok')}</strong></p>"
        "<ul>"
        f"<li>Matched: <code>{receipt.get('matched')}</code></li>"
        f"<li>Candidate count: <code>{receipt.get('candidate_count')}</code></li>"
        f"<li>Shortlist count: <code>{receipt.get('shortlist_count')}</code></li>"
        f"<li>Receipt kind: <code>{receipt.get('receipt_kind')}</code></li>"
        f"<li>Generated at: <code>{receipt.get('generated_at')}</code></li>"
        "</ul>"
        "<table><tr><th>Receipt</th><th>Value</th></tr>"
        f"<tr><td>marker</td><td><code>{receipt.get('receipt_marker')}</code></td></tr>"
        f"<tr><td>source marker</td><td><code>{receipt.get('source_marker')}</code></td></tr>"
        "</table>"
        "</section>"
    )


def build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_response(
    prompt: str = "research archive candidate shortlist dashboard web admin dispatch receipt",
    *,
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    limit: int = 10,
    preview_limit: int = 3,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_prompt(prompt)
    matched = matches_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_prompt(normalized_prompt)

    integration_response = _call_integration_response(
        normalized_prompt,
        intake_dir=Path(intake_dir),
        limit=limit,
        preview_limit=preview_limit,
        write_outputs=write_outputs,
        json_requested=True,
    )

    receipt = _build_receipt_payload(
        integration_response,
        matched=matched,
        prompt=normalized_prompt,
    )

    output_paths: dict[str, str] = {}
    if write_outputs:
        output_paths = _write_receipt_outputs(receipt, Path(intake_dir))

    response = dict(receipt)
    response["output_paths"] = output_paths
    response["html"] = _receipt_html(response)

    if json_requested:
        response["json"] = {
            "ok": response.get("ok"),
            "matched": response.get("matched"),
            "receipt_marker": MARKER,
            "data_link_receipt": DATA_LINK_RECEIPT,
            "candidate_count": response.get("candidate_count"),
            "shortlist_count": response.get("shortlist_count"),
            "has_literal_table": "<table>" in response.get("html", ""),
            "has_non_destructive": 'data-link-destructive="false"' in response.get("html", ""),
            "output_paths": output_paths,
        }

    return response


def validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / "intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_response(
            "show research archive candidate shortlist dashboard web admin dispatch receipt",
            intake_dir=intake_dir,
            limit=2,
            preview_limit=2,
            write_outputs=True,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("dispatch receipt response should be ok")
        if not response.get("matched"):
            failures.append("dispatch receipt response should be matched")
        if response.get("receipt_marker") != MARKER:
            failures.append("dispatch receipt marker mismatch")
        if response.get("receipt_kind") != RECEIPT_KIND:
            failures.append("dispatch receipt kind mismatch")
        if response.get("data_link_receipt") != DATA_LINK_RECEIPT:
            failures.append("dispatch receipt data-link mismatch")

        html_text = response.get("html") or ""
        if DATA_LINK_RECEIPT not in html_text:
            failures.append("dispatch receipt html missing data-link receipt")
        if 'data-link-destructive="false"' not in html_text:
            failures.append("dispatch receipt html should be explicitly non-destructive")
        if "<table>" not in html_text:
            failures.append("dispatch receipt html missing receipt table")
        if response.get("shortlist_count", 0) < 1:
            failures.append("dispatch receipt should include shortlist candidates")

        output_paths = response.get("output_paths") or {}
        for key in ("receipt_json", "receipt_report"):
            value = output_paths.get(key)
            if not value:
                failures.append(f"dispatch receipt missing output path: {key}")
            elif not Path(value).exists():
                failures.append(f"dispatch receipt output path does not exist: {key}")

        payload = response.get("json") or {}
        if payload.get("receipt_marker") != MARKER:
            failures.append("dispatch receipt JSON marker mismatch")
        if not payload.get("has_literal_table"):
            failures.append("dispatch receipt JSON should confirm literal table")

    return failures

def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch receipt FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="research archive candidate shortlist dashboard web admin dispatch receipt")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE_DIR)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-write-outputs", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    response = build_research_candidate_shortlist_dashboard_web_admin_dispatch_receipt_response(
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
        print(response.get("html") or response.get("receipt_marker") or MARKER)


if __name__ == "__main__":
    main()
