#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import html
import re
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DASHBOARD_HTML = ROOT / ".link/dashboard/self_learning_dashboard.html"
ACTION_LOG = ROOT / ".link/dashboard/action_dispatch.log"


def run_cmd(args: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, p.stdout
    except Exception as exc:
        return 99, f"{type(exc).__name__}: {exc}"


def log_action(message: str) -> None:
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ACTION_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


def latest_pending_draft_id() -> str:
    pending = ROOT / ".link/patch_drafts/pending"
    drafts = sorted(pending.glob("*.json"))
    if not drafts:
        return ""
    return drafts[-1].stem


def clear_current_draft(reason: str) -> str:
    draft_id = latest_pending_draft_id()
    if not draft_id:
        return "No current pending draft to clear.\n"

    code, out = run_cmd(
        [
            "python3",
            "link_approval_patch_draft_queue.py",
            "decide",
            "--action",
            "try_again",
            "--draft-id",
            draft_id,
            "--feedback",
            reason,
            "--format",
            "markdown",
        ],
        timeout=120,
    )
    return f"$ clear current draft {draft_id}\nexit={code}\n{out}\n"


def _rebuild_dashboard_raw() -> str:
    run_cmd(["python3", "link_dashboard_proposal_refill.py", "--write", "--format", "markdown"], timeout=120)
    code, out = run_cmd(["python3", "link_self_learning_dashboard.py", "render", "--format", "html", "--write"], timeout=120)

    if DASHBOARD_HTML.exists():
        page = DASHBOARD_HTML.read_text(encoding="utf-8", errors="replace")
    else:
        page = "<html><body><h1>Dashboard render failed</h1></body></html>"

    if code != 0:
        page = (
            "<!doctype html><html><body>"
            "<h1>Dashboard render command failed</h1>"
            f"<pre>{html.escape(out)}</pre>"
            + page
            + "</body></html>"
        )

    return inject_hard_recovery_controls(page)


def hard_recovery_controls() -> str:
    draft_id = latest_pending_draft_id()
    q_draft = urllib.parse.quote(draft_id)
    q_fb = urllib.parse.quote("Clicked from HARD LINK recovery controls.")

    yes_href = f"/action?action=yes&draft_id={q_draft}&feedback={q_fb}"
    no_href = f"/action?action=no&draft_id={q_draft}&feedback={q_fb}"
    retry_href = f"/action?action=try_again&draft_id={q_draft}&feedback={q_fb}"
    clear_href = f"/action?action=clear_bugged_draft&draft_id={q_draft}&feedback={q_fb}"
    gen_href = f"/action?action=generate_new_draft&feedback={q_fb}"
    refresh_href = f"/action?action=refresh&t={int(time.time())}"
    ping_href = f"/__ping?t={int(time.time())}"

    disabled = "opacity:.35;pointer-events:none;filter:grayscale(1);" if not draft_id else ""

    return f"""
<div id="hard-recovery-controls" style="border:3px solid #fbbf24;background:#111827;color:#e5e7eb;border-radius:14px;padding:16px;margin:16px 0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
  <h2 style="margin-top:0;color:#f9fafb;">Emergency Hard-Link Controls</h2>
  <p><strong>These are normal links, not JavaScript buttons.</strong> If these do not work, the browser is not hitting the live server.</p>
  <p>Current draft: <code>{html.escape(draft_id or "none")}</code></p>
  <p>
    <a href="{yes_href}" style="{disabled}display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#62d26f;color:#052e16;font-weight:900;text-decoration:none;">YES HARD LINK</a>
    <a href="{no_href}" style="{disabled}display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#ef6262;color:#450a0a;font-weight:900;text-decoration:none;">NO HARD LINK</a>
    <a href="{retry_href}" style="{disabled}display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#f2c14e;color:#422006;font-weight:900;text-decoration:none;">TRY AGAIN HARD LINK</a>
    <a href="{clear_href}" style="display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#fb7185;color:#450a0a;font-weight:900;text-decoration:none;">CLEAR CURRENT DRAFT</a>
    <a href="{gen_href}" style="display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#34d399;color:#022c22;font-weight:900;text-decoration:none;">GENERATE NEW DRAFT</a>
    <a href="{refresh_href}" style="display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#60a5fa;color:#082f49;font-weight:900;text-decoration:none;">REFRESH HARD LINK</a>
    <a href="{ping_href}" style="display:inline-block;margin:4px;padding:10px 13px;border-radius:9px;background:#e5e7eb;color:#111827;font-weight:900;text-decoration:none;">PING SERVER</a>
  </p>
</div>
"""


def inject_hard_recovery_controls(page: str) -> str:
    if "Emergency Hard-Link Controls" in page:
        return page

    controls = hard_recovery_controls()

    if "<body>" in page:
        return page.replace("<body>", "<body>\n" + controls, 1)

    return controls + page


def action_result_html(action: str, draft_id: str, feedback: str, outputs: list[str]) -> str:
    safe_outputs = html.escape("\n\n".join(outputs))
    return f"""
<div style="border:3px solid #60a5fa;background:#020617;color:#e5e7eb;border-radius:14px;padding:16px;margin:16px 0;">
  <h2>Action Result</h2>
  <p><strong>Action:</strong> <code>{html.escape(action)}</code></p>
  <p><strong>Draft ID:</strong> <code>{html.escape(draft_id or "(none)")}</code></p>
  <p><strong>Feedback:</strong> <code>{html.escape(feedback or "(none)")}</code></p>
  <pre style="white-space:pre-wrap;">{safe_outputs}</pre>
</div>
"""


def dispatch_action(fields: dict[str, list[str]], source: str) -> str:
    def field(name: str, default: str = "") -> str:
        values = fields.get(name) or []
        return values[0] if values else default

    action = field("action", "refresh")
    draft_id = field("draft_id", "") or latest_pending_draft_id()
    feedback = field("feedback", "Clicked from dashboard.")

    log_action(f"{source} action={action!r} draft_id={draft_id!r} fields={fields!r}")

    outputs: list[str] = []

    if action in {"yes", "no", "try_again"}:
        if not draft_id:
            outputs.append("No draft_id available, so approval decision was not run.")
        else:
            code, out = run_cmd(
                [
                    "python3",
                    "link_approval_patch_draft_queue.py",
                    "decide",
                    "--action",
                    action,
                    "--draft-id",
                    draft_id,
                    "--feedback",
                    feedback,
                    "--format",
                    "markdown",
                ],
                timeout=120,
            )
            outputs.append(f"$ approval decide {action} {draft_id}\nexit={code}\n{out}")

        code, out = run_cmd(
            ["python3", "link_dashboard_proposal_refill.py", "--force-new", "--write", "--format", "markdown"],
            timeout=120,
        )
        outputs.append(f"$ refill after decision\nexit={code}\n{out}")

    elif action in {"generate_new", "generate_new_draft", "find_growth"}:
        outputs.append(clear_current_draft("Cleared by GENERATE NEW DRAFT hard-link recovery control."))
        code, out = run_cmd(
            [
                "python3",
                "link_dashboard_proposal_refill.py",
                "--clear-bugged",
                "--force-new",
                "--write",
                "--format",
                "markdown",
            ],
            timeout=120,
        )
        outputs.append(f"$ generate new draft\nexit={code}\n{out}")

    elif action in {"clear_bugged", "clear_bugged_draft", "reconcile"}:
        outputs.append(clear_current_draft("Cleared by CLEAR BUGGED DRAFT hard-link recovery control."))
        code, out = run_cmd(
            ["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--write", "--format", "markdown"],
            timeout=120,
        )
        outputs.append(f"$ clear bugged/refill\nexit={code}\n{out}")

    elif action == "run_tick":
        code, out = run_cmd(["python3", "link_autonomous_tick_runner.py"], timeout=180)
        outputs.append(f"$ run tick\nexit={code}\n{out}")
        code, out = run_cmd(
            ["python3", "link_dashboard_proposal_refill.py", "--write", "--format", "markdown"],
            timeout=120,
        )
        outputs.append(f"$ refill after tick\nexit={code}\n{out}")

    else:
        outputs.append("Refresh/no-op action received.")

    page = rebuild_dashboard()
    result = action_result_html(action, draft_id, feedback, outputs)

    if "<body>" in page:
        page = page.replace("<body>", "<body>\n" + result, 1)
    else:
        page = result + page

    return page


class Handler(BaseHTTPRequestHandler):
    def send_html(self, page: str, status: int = 200) -> None:
        raw = page.encode("utf-8", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(raw)

    def send_text(self, text: str, status: int = 200) -> None:
        raw = text.encode("utf-8", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/__ping":
            log_action(f"PING path={self.path!r}")
            self.send_text(f"pong {time.strftime('%Y-%m-%dT%H:%M:%S')} pid-live\n")
            return

        if parsed.path == "/action":
            fields = urllib.parse.parse_qs(parsed.query)
            page = dispatch_action(fields, source=f"GET {self.path}")
            self.send_html(page)
            return

        self.send_html(rebuild_dashboard())

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/action":
            self.send_html(rebuild_dashboard(), status=404)
            return

        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        fields = urllib.parse.parse_qs(body)
        page = dispatch_action(fields, source=f"POST {self.path}")
        self.send_html(page)

    def log_message(self, fmt: str, *args: object) -> None:
        log_action("HTTP " + (fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    if args.smoke:
        page = rebuild_dashboard()
        assert "Emergency Hard-Link Controls" in page
        assert "YES HARD LINK" in page
        assert "GENERATE NEW DRAFT" in page
        print("self-learning dashboard web admin smoke OK")
        return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving Link self-learning dashboard at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()



# BEGIN LINK APPROVAL CARD DOUBLE REPAIR
def _as_lines(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip("- ").strip() for x in value.splitlines() if x.strip()]
    return [str(value).strip()]


def _current_approval_text_from_pending_json(page: str) -> str:
    """Build one canonical Approval Target text from the current pending JSON."""
    m = re.search(r'<section\b[^>]*class=["\']approval-target-card["\'][^>]*data-draft-id=["\']([^"\']*)["\']', page)
    draft_id = m.group(1).strip() if m else ""

    if not draft_id:
        return "## Approval Target\n\nStatus: **not ready**\nReason: No pending approval draft is available.\n"

    draft_file = ROOT / ".link/patch_drafts/pending" / f"{draft_id}.json"
    md_file = ROOT / ".link/patch_drafts/pending" / f"{draft_id}.md"

    try:
        data = json.loads(draft_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return (
            "## Approval Target\n\n"
            f"- Draft ID: `{draft_id}`\n"
            f"- Draft file: `{draft_file}`\n"
            f"- Status: **broken**\n"
            f"- Reason: Could not read pending JSON: {type(exc).__name__}: {exc}\n"
        )

    task_id = data.get("task_id") or data.get("task") or ""
    title = data.get("title") or data.get("task_title") or data.get("name") or ""
    status = data.get("status") or "waiting_approval"
    risk = data.get("risk") or "unknown"
    proposal_hash = data.get("proposal_hash") or data.get("hash") or ""

    why = data.get("why") or data.get("reason") or ""
    plan = _as_lines(data.get("proposed_plan") or data.get("plan"))
    files = _as_lines(data.get("files_affected") or data.get("affected_files") or data.get("files"))
    tests = _as_lines(data.get("tests") or data.get("checks") or data.get("recommended_tests"))
    receipts = _as_lines(data.get("receipts"))

    lines = [
        "## Approval Target",
        "",
        "Contract version: `LU110-dashboard-approval-contract-v1`",
        "",
        f"- Draft ID: `{draft_id}`",
        f"- Draft file: `{draft_file}`",
        f"- Markdown file: `{md_file}`",
        f"- Proposal hash: `{proposal_hash}`",
        f"- Status: **{status}**",
        f"- Task: `{task_id}` — **{title}**",
        f"- Risk: **{risk}**",
        "- YES enabled: **True**",
        "",
    ]

    if why:
        lines += ["### Why", "", str(why), ""]

    if plan:
        lines += ["### Proposed Plan"]
        lines += [f"- {x}" for x in plan]
        lines.append("")

    if files:
        lines += ["### Files / Areas Affected"]
        lines += [f"- `{x}`" for x in files]
        lines.append("")

    if tests:
        lines += ["### Tests / Checks"]
        lines += [f"- `{x}`" for x in tests]
        lines.append("")

    if receipts:
        lines += ["### Receipts"]
        lines += [f"- `{x}`" for x in receipts]
        lines.append("")

    lines += [
        "### Button Meaning",
        "- **YES** approves this exact visible draft/hash only.",
        "- **NO** rejects this exact visible draft and stores feedback.",
        "- **TRY AGAIN** moves this exact visible draft to retry with feedback.",
        "",
        "### Exact Commands",
        f"- YES: `python3 link_approval_patch_draft_queue.py decide --action yes --draft-id '{draft_id}' --feedback 'Approved from dashboard.' --format markdown`",
        f"- NO: `python3 link_approval_patch_draft_queue.py decide --action no --draft-id '{draft_id}' --feedback 'Rejected from dashboard.' --format markdown`",
        f"- TRY AGAIN: `python3 link_approval_patch_draft_queue.py decide --action try_again --draft-id '{draft_id}' --feedback 'Try again with Brandon feedback.' --format markdown`",
        "",
    ]

    return "\n".join(lines)


def _repair_approval_card(page: str) -> str:
    approval_text = _current_approval_text_from_pending_json(page)
    safe = html.escape(approval_text, quote=False)

    def fix_section(match):
        section = match.group(0)

        section = re.sub(
            r'(<textarea\b[^>]*\bid=["\']approval-proposal-copy["\'][^>]*>).*?(</textarea>)',
            lambda m: m.group(1) + safe + m.group(2),
            section,
            count=1,
            flags=re.S,
        )

        section = re.sub(
            r'(<pre>).*?(</pre>)',
            lambda m: m.group(1) + safe + m.group(2),
            section,
            count=1,
            flags=re.S,
        )

        return section

    page = re.sub(
        r'<section\b[^>]*class=["\']approval-target-card["\'][\s\S]*?</section>',
        fix_section,
        page,
        count=1,
    )

    return page + "\n<!-- approval card textarea and visible pre repaired from pending draft JSON -->\n"


def rebuild_dashboard() -> str:
    return _repair_approval_card(_rebuild_dashboard_raw())
# END LINK APPROVAL CARD DOUBLE REPAIR

if __name__ == "__main__":
    main()
