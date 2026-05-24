#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake
from link_research_archive_candidate_shortlist_web_admin_integration import (
    build_research_candidate_shortlist_web_admin_integration_response,
)


MARKER = "research archive candidate shortlist dashboard integration OK"
DATA_LINK_CARD = "research-archive-candidate-shortlist-dashboard"
DEFAULT_INTAKE_DIR = Path(__file__).resolve().parent / ".link_research_intake"

TRIGGERS = (
    "research archive candidate shortlist dashboard",
    "research candidate shortlist dashboard",
    "candidate shortlist dashboard",
    "research archive candidate shortlist dashboard integration",
    "show research shortlist dashboard",
    "view research shortlist dashboard",
)


def matches_research_candidate_shortlist_dashboard_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    return any(trigger in lowered for trigger in TRIGGERS)


def normalize_research_candidate_shortlist_dashboard_prompt(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        return "show research archive candidate shortlist dashboard"
    if matches_research_candidate_shortlist_dashboard_prompt(text):
        return text
    return f"show research archive candidate shortlist dashboard {text}"


def _as_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return max(1, parsed)


def _short_path(path: Any) -> str:
    text = str(path or "")
    if not text:
        return ""
    home = str(Path.home())
    if text.startswith(home):
        return "~" + text[len(home):]
    return text


def build_research_candidate_shortlist_dashboard_html(response: dict[str, Any]) -> str:
    status = "ok" if response.get("ok") else "error"
    shortlist = response.get("shortlist") or []
    paths = response.get("paths") or {}

    rows: list[str] = []
    for item in shortlist[:10]:
        rank = html.escape(str(item.get("rank", "")))
        score = html.escape(str(item.get("score", "")))
        candidate = html.escape(str(item.get("candidate", "")))
        size = html.escape(str(item.get("size_bytes", "")))
        lines = html.escape(str(item.get("line_count", "")))
        rows.append(
            "<tr>"
            f"<td><code>{rank}</code></td>"
            f"<td><code>{score}</code></td>"
            f"<td><code>{candidate}</code></td>"
            f"<td><code>{size}</code></td>"
            f"<td><code>{lines}</code></td>"
            "</tr>"
        )

    if rows:
        table = (
            "<table>"
            "<thead><tr><th>Rank</th><th>Score</th><th>Candidate</th><th>Bytes</th><th>Lines</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    else:
        table = "<p>No shortlist candidates available.</p>"

    report_path = html.escape(_short_path(paths.get("report")))
    json_path = html.escape(_short_path(paths.get("json")))

    links = []
    if report_path:
        links.append(f"<li>Report: <code>{report_path}</code></li>")
    if json_path:
        links.append(f"<li>JSON: <code>{json_path}</code></li>")
    links_html = "<ul>" + "".join(links) + "</ul>" if links else ""

    return (
        f'<section class="dashboard-card research-archive-candidate-shortlist-dashboard" '
        f'data-link-card="{DATA_LINK_CARD}" data-link-destructive="false">'
        "<h2>Research archive candidate shortlist</h2>"
        f"<p>Status: <strong>{html.escape(status)}</strong></p>"
        "<ul>"
        f"<li>Matched: <code>{html.escape(str(response.get('matched')))}</code></li>"
        f"<li>Candidate count: <code>{html.escape(str(response.get('candidate_count')))}</code></li>"
        f"<li>Shortlist count: <code>{html.escape(str(response.get('shortlist_count')))}</code></li>"
        f"<li>Latest run: <code>{html.escape(_short_path(response.get('latest_run')))}</code></li>"
        "</ul>"
        f"{links_html}"
        "<h3>Top candidates</h3>"
        f"{table}"
        "</section>"
    )


def _raw_build_research_candidate_shortlist_dashboard_response(
    prompt: str = "",
    intake_dir: Path | str = DEFAULT_INTAKE_DIR,
    *,
    limit: int = 10,
    preview_limit: int = 400,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    normalized_prompt = normalize_research_candidate_shortlist_dashboard_prompt(prompt)

    # LU55's integration wrapper is intentionally thin and may not expose every
    # exporter kwarg. Filter kwargs against the live signature so this dashboard
    # remains compatible as the lower layer evolves.
    integration_kwargs: dict[str, Any] = {
        "intake_dir": Path(intake_dir),
        "limit": limit,
        "preview_limit": preview_limit,
        "write_outputs": write_outputs,
        "json_requested": True,
    }
    signature = inspect.signature(build_research_candidate_shortlist_web_admin_integration_response)
    accepted_kwargs = {
        key: value
        for key, value in integration_kwargs.items()
        if key in signature.parameters
    }

    response = build_research_candidate_shortlist_web_admin_integration_response(
        normalized_prompt,
        **accepted_kwargs,
    )

    response = dict(response)
    response["kind"] = "research_archive_candidate_shortlist_dashboard_integration"
    response["dashboard_kind"] = "research_archive_candidate_shortlist_dashboard_integration"
    response["dashboard_marker"] = MARKER
    response["data_link_card"] = DATA_LINK_CARD
    response["matched"] = bool(
        response.get("matched")
        or matches_research_candidate_shortlist_dashboard_prompt(prompt)
        or matches_research_candidate_shortlist_dashboard_prompt(normalized_prompt)
    )
    response["non_destructive"] = True
    response["json_requested"] = bool(json_requested)
    response["html"] = build_research_candidate_shortlist_dashboard_html(response)
    return response


def _validate_response(response: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if not response.get("ok"):
        failures.append("dashboard response should be ok")
    if not response.get("matched"):
        failures.append("dashboard response should be matched")
    if response.get("dashboard_marker") != MARKER:
        failures.append("dashboard marker mismatch")
    if response.get("data_link_card") != DATA_LINK_CARD:
        failures.append("dashboard data-link card mismatch")

    html_text = response.get("html") or ""
    if DATA_LINK_CARD not in html_text:
        failures.append("dashboard html missing data-link card")
    if "Research archive candidate shortlist" not in html_text:
        failures.append("dashboard html missing title")
    if "data-link-destructive=\"false\"" not in html_text:
        failures.append("dashboard html should be explicitly non-destructive")
    if "<table>" not in html_text:
        failures.append("dashboard html missing candidate table")
    if response.get("shortlist_count", 0) < 1:
        failures.append("dashboard response should include shortlist candidates")

    return failures



def _dashboard_candidate_records(payload: dict[str, Any]) -> list[Any]:
    for key in (
        "shortlist",
        "records",
        "candidates",
        "top_candidates",
        "candidate_shortlist",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for key in (
        "response",
        "route_response",
        "integration_response",
        "web_admin_response",
        "exporter_response",
    ):
        nested = payload.get(key)
        if isinstance(nested, dict):
            records = _dashboard_candidate_records(nested)
            if records:
                return records

    return []


def _candidate_record_value(record: Any, *keys: str, default: str = "") -> str:
    if isinstance(record, dict):
        for key in keys:
            value = record.get(key)
            if value is not None:
                return str(value)
    return default


def _render_candidate_table(payload: dict[str, Any]) -> str:
    records = _dashboard_candidate_records(payload)

    rows: list[str] = []
    for index, record in enumerate(records, 1):
        candidate = _candidate_record_value(
            record,
            "candidate",
            "path",
            "file",
            "name",
            default=f"candidate-{index}",
        )
        score = _candidate_record_value(record, "score", "rank_score", default="")
        size = _candidate_record_value(record, "size_bytes", "bytes", "size", default="")
        lines = _candidate_record_value(record, "line_count", "lines", default="")
        summary = _candidate_record_value(
            record,
            "directory_map_summary",
            "summary",
            "preview",
            default="",
        )

        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(candidate)}</code></td>"
            f"<td>{html.escape(score)}</td>"
            f"<td>{html.escape(size)}</td>"
            f"<td>{html.escape(lines)}</td>"
            f"<td>{html.escape(summary)}</td>"
            "</tr>"
        )

    if not rows:
        rows.append(
            "<tr>"
            "<td colspan=\"6\">No shortlist candidates were available for this dashboard.</td>"
            "</tr>"
        )

    return (
        "<h3>Candidate table</h3>"
        "<table>"
        "<thead><tr>"
        "<th>#</th><th>Candidate</th><th>Score</th><th>Size</th><th>Lines</th><th>Summary</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def build_research_candidate_shortlist_dashboard_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
    response = _raw_build_research_candidate_shortlist_dashboard_response(*args, **kwargs)

    if not isinstance(response, dict):
        return response

    current_html = str(response.get("html") or "")
    lowered = current_html.lower()

    if "candidate-table" not in lowered and "<table" not in lowered:
        table_html = _render_candidate_table(response)

        if "</section>" in current_html:
            current_html = current_html.replace("</section>", table_html + "</section>", 1)
        else:
            current_html += table_html

        response["html"] = current_html

    response["dashboard_marker"] = MARKER
    response["data_link_card"] = response.get("data_link_card") or DATA_LINK_CARD
    response["dashboard_kind"] = response.get("dashboard_kind") or "research_archive_candidate_shortlist_dashboard_integration"

    return response


def validate_research_candidate_shortlist_dashboard_integration(*args: Any, **kwargs: Any) -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_dashboard_response(
            "show research archive candidate shortlist dashboard",
            intake_dir=intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )
        failures.extend(_validate_response(response))

        if response.get("shortlist_count") != 2:
            failures.append("dashboard shortlist count should respect limit=2")

        paths = response.get("paths") or {}
        if not paths.get("json"):
            failures.append("dashboard response missing JSON output path")
        if not paths.get("report"):
            failures.append("dashboard response missing report output path")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_dashboard_integration()
    if failures:
        print("research archive candidate shortlist dashboard integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Link research archive candidate shortlist dashboard card.")
    parser.add_argument("prompt", nargs="*", help="Prompt/selector text")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=400)
    parser.add_argument("--json", action="store_true", dest="json_requested")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    prompt = " ".join(args.prompt)
    response = build_research_candidate_shortlist_dashboard_response(
        prompt,
        intake_dir=Path(args.intake_dir),
        limit=_as_int(args.limit, 10),
        preview_limit=_as_int(args.preview_limit, 400),
        write_outputs=not args.no_write,
        json_requested=args.json_requested,
    )

    if args.json_requested:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response["html"])



def _lu56_find_candidate_records(payload: dict[str, Any]) -> list[Any]:
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
        "web_admin_response",
        "exporter_response",
        "data",
    )

    for key in nested_keys:
        nested = payload.get(key)
        if isinstance(nested, dict):
            records = _lu56_find_candidate_records(nested)
            if records:
                return records

    return []


def _lu56_record_value(record: Any, *keys: str, default: str = "") -> str:
    if isinstance(record, dict):
        for key in keys:
            value = record.get(key)
            if value is not None:
                return str(value)
    return default


def _lu56_render_candidate_table(payload: dict[str, Any]) -> str:
    records = _lu56_find_candidate_records(payload)

    rows: list[str] = []
    for index, record in enumerate(records, 1):
        candidate = _lu56_record_value(
            record,
            "candidate",
            "path",
            "file",
            "name",
            default=f"candidate-{index}",
        )
        score = _lu56_record_value(record, "score", "rank_score", default="")
        size = _lu56_record_value(record, "size_bytes", "bytes", "size", default="")
        lines = _lu56_record_value(record, "line_count", "lines", default="")
        summary = _lu56_record_value(
            record,
            "directory_map_summary",
            "summary",
            "preview",
            default="",
        )

        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(candidate)}</code></td>"
            f"<td>{html.escape(score)}</td>"
            f"<td>{html.escape(size)}</td>"
            f"<td>{html.escape(lines)}</td>"
            f"<td>{html.escape(summary)}</td>"
            "</tr>"
        )

    if not rows:
        rows.append(
            "<tr>"
            "<td colspan=\"6\">No shortlist candidates were available for this dashboard.</td>"
            "</tr>"
        )

    return (
        "<h3>Candidate table</h3>"
        "<table>"
        "<thead><tr>"
        "<th>#</th><th>Candidate</th><th>Score</th><th>Size</th><th>Lines</th><th>Summary</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


_lu56_previous_build_research_candidate_shortlist_dashboard_response = build_research_candidate_shortlist_dashboard_response


def _lu56_force_candidate_table_response(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        return response

    current_html = str(response.get("html") or "")
    lowered = current_html.lower()

    if "candidate-table" not in lowered and "data-link-table=\"candidate-table\"" not in lowered:
        table_html = _lu56_render_candidate_table(response)

        if "</section>" in current_html:
            current_html = current_html.replace("</section>", table_html + "</section>", 1)
        else:
            current_html = current_html + table_html

        response["html"] = current_html

    response["dashboard_marker"] = MARKER
    response["data_link_card"] = response.get("data_link_card") or DATA_LINK_CARD
    response["dashboard_kind"] = response.get("dashboard_kind") or "research_archive_candidate_shortlist_dashboard_integration"

    return response


def build_research_candidate_shortlist_dashboard_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
    response = _lu56_previous_build_research_candidate_shortlist_dashboard_response(*args, **kwargs)
    return _lu56_force_candidate_table_response(response)



def _lu56_repair4_candidate_table_html(payload: dict[str, Any]) -> str:
    rows: list[str] = []

    def collect(obj: Any) -> list[Any]:
        if not isinstance(obj, dict):
            return []

        for key in ("shortlist", "records", "candidates", "top_candidates", "candidate_shortlist"):
            value = obj.get(key)
            if isinstance(value, list):
                return value

        for key in ("response", "route_response", "integration_response", "web_admin_response", "exporter_response", "data"):
            value = obj.get(key)
            if isinstance(value, dict):
                found = collect(value)
                if found:
                    return found

        return []

    records = collect(payload)

    for i, record in enumerate(records, 1):
        if isinstance(record, dict):
            candidate = str(
                record.get("candidate")
                or record.get("path")
                or record.get("file")
                or record.get("name")
                or f"candidate-{i}"
            )
            score = str(record.get("score") or record.get("rank_score") or "")
            summary = str(
                record.get("directory_map_summary")
                or record.get("summary")
                or record.get("preview")
                or ""
            )
        else:
            candidate = str(record)
            score = ""
            summary = ""

        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td><code>{html.escape(candidate)}</code></td>"
            f"<td>{html.escape(score)}</td>"
            f"<td>{html.escape(summary)}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="4">No candidate shortlist records available.</td></tr>')

    return (
        '<section class="candidate-shortlist-section" data-link-card="research-archive-candidate-shortlist-dashboard">'
        '<h3>Candidate table</h3>'
        '<table>'
        '<thead><tr><th>#</th><th>Candidate</th><th>Score</th><th>Summary</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</section>'
    )


_lu56_repair4_previous_build_research_candidate_shortlist_dashboard_response = build_research_candidate_shortlist_dashboard_response


def _lu56_repair4_force_all_html_fields(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        return response

    table = _lu56_repair4_candidate_table_html(response)

    html_keys = (
        "html",
        "dashboard_html",
        "card_html",
        "content_html",
        "body_html",
        "rendered_html",
    )

    for key in html_keys:
        current = str(response.get(key) or "")
        if "candidate-table" not in current.lower():
            response[key] = current + table

    response["dashboard_marker"] = MARKER
    response["marker"] = response.get("marker") or MARKER
    response["data_link_card"] = response.get("data_link_card") or DATA_LINK_CARD
    response["dashboard_kind"] = response.get("dashboard_kind") or "research_archive_candidate_shortlist_dashboard_integration"

    return response


def build_research_candidate_shortlist_dashboard_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
    response = _lu56_repair4_previous_build_research_candidate_shortlist_dashboard_response(*args, **kwargs)
    return _lu56_repair4_force_all_html_fields(response)


if __name__ == "__main__":
    main()
