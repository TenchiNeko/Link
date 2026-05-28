
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any


def _class_for_recommendation(recommendation: str) -> str:
    rec = (recommendation or "").upper()
    if rec == "NO_ROLLBACK_NEEDED":
        return "ok"
    if rec == "ADVISE_ROLLBACK_TO_LAST_PASS":
        return "warn"
    if rec in {"BLOCK_ROLLBACK_NO_KNOWN_GOOD", "NO_EVIDENCE"}:
        return "bad"
    return "warn"


def render_rollback_advisor_panel(advice: dict[str, Any]) -> str:
    recommendation = str(advice.get("recommendation") or "UNKNOWN")
    css_class = _class_for_recommendation(recommendation)
    reason = str(advice.get("reason") or "")
    current_head = str(advice.get("current_head") or "-")
    rollback_candidate = str(advice.get("rollback_candidate") or "-")
    latest_status = str(advice.get("latest_status") or "UNKNOWN")
    latest_archive = str(advice.get("latest_archive") or "-")

    actions = advice.get("safe_actions") or []
    recent = advice.get("recent_evidence") or []

    parts = [
        '<section class="card rollback-advisor">',
        '<h2>Evidence-aware rollback advisor</h2>',
        f'<div class="badge {escape(css_class)}">{escape(recommendation)}</div>',
        '<dl>',
        f'<dt>Reason</dt><dd>{escape(reason)}</dd>',
        f'<dt>Current HEAD</dt><dd><code>{escape(current_head)}</code></dd>',
        f'<dt>Rollback candidate</dt><dd><code>{escape(rollback_candidate)}</code></dd>',
        f'<dt>Latest evidence</dt><dd>{escape(latest_archive)} [{escape(latest_status)}]</dd>',
        '</dl>',
    ]

    if actions:
        parts.append('<h3>Safe actions</h3>')
        parts.append('<ul>')
        for action in actions:
            parts.append(f'<li>{escape(str(action))}</li>')
        parts.append('</ul>')

    if recent:
        parts.append('<h3>Recent evidence</h3>')
        parts.append('<table>')
        parts.append('<thead><tr><th>Archive</th><th>Status</th><th>Commit</th></tr></thead>')
        parts.append('<tbody>')
        for row in recent:
            parts.append(
                '<tr>'
                f'<td>{escape(str(row.get("archive") or ""))}</td>'
                f'<td>{escape(str(row.get("status") or ""))}</td>'
                f'<td><code>{escape(str(row.get("commit") or "-"))}</code></td>'
                '</tr>'
            )
        parts.append('</tbody></table>')

    parts.append('</section>')
    return "\n".join(parts)


def rollback_advisor_css() -> str:
    return """
.rollback-advisor .badge {
  display: inline-block;
  padding: 0.35rem 0.6rem;
  border-radius: 0.5rem;
  font-weight: 700;
}
.rollback-advisor .ok { background: #d1fae5; color: #065f46; }
.rollback-advisor .warn { background: #fef3c7; color: #92400e; }
.rollback-advisor .bad { background: #fee2e2; color: #991b1b; }
.rollback-advisor code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.rollback-advisor table { width: 100%; border-collapse: collapse; }
.rollback-advisor th, .rollback-advisor td { text-align: left; padding: 0.35rem; border-bottom: 1px solid #ddd; }
""".strip()


def render_live_panel(root: str | Path | None = None) -> str:
    from evidence_rollback_advisor import advise_from_archive

    advice = advise_from_archive(root)
    return render_rollback_advisor_panel(advice)


def dashboard_payload(root: str | Path | None = None) -> dict[str, Any]:
    from evidence_rollback_advisor import advise_from_archive

    advice = advise_from_archive(root)
    return {
        "component": "rollback_advisor",
        "html": render_rollback_advisor_panel(advice),
        "css": rollback_advisor_css(),
        "advice": advice,
    }


def self_test() -> list[str]:
    problems = []

    advice = {
        "recommendation": "ADVISE_ROLLBACK_TO_LAST_PASS",
        "reason": "Most recent evidence failed; a prior passing healthcheck archive exists.",
        "current_head": "bad222",
        "rollback_candidate": "good111",
        "latest_archive": "20260102-fail",
        "latest_status": "FAIL",
        "safe_actions": ["Inspect diff", "Create review branch"],
        "recent_evidence": [
            {"archive": "20260102-fail", "status": "FAIL", "commit": "bad222"},
            {"archive": "20260101-pass", "status": "PASS", "commit": "good111"},
        ],
    }

    html = render_rollback_advisor_panel(advice)
    if "Evidence-aware rollback advisor" not in html:
        problems.append("panel_missing_title")
    if "ADVISE_ROLLBACK_TO_LAST_PASS" not in html:
        problems.append("panel_missing_recommendation")
    if "good111" not in html:
        problems.append("panel_missing_candidate")
    if "rollback-advisor" not in html:
        problems.append("panel_missing_css_class")

    css = rollback_advisor_css()
    if ".rollback-advisor" not in css:
        problems.append("css_missing_component_selector")

    payload = {
        "component": "rollback_advisor",
        "html": html,
        "css": css,
        "advice": advice,
    }
    if payload["component"] != "rollback_advisor":
        problems.append("payload_component_mismatch")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Render rollback advisor dashboard panel.")
    parser.add_argument("--root", default=None, help="Healthcheck evidence archive root.")
    parser.add_argument("--json", action="store_true", help="Print dashboard payload JSON.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("rollback advisor dashboard FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("rollback advisor dashboard OK")
        return 0

    payload = dashboard_payload(args.root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["html"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
