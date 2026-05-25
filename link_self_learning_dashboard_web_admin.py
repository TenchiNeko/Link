#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DASHBOARD_HTML = ROOT / ".link/dashboard/self_learning_dashboard.html"


def run_cmd(args: list[str], timeout: int = 90) -> tuple[int, str]:
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
    except subprocess.TimeoutExpired as e:
        return 124, f"Timed out: {' '.join(args)}\n{e}"


def error_page(title: str, body: str) -> str:
    return f"""<!doctype html><html><body style="font-family:sans-serif;background:#111827;color:#e5e7eb;padding:24px;">
<h1>{html.escape(title)}</h1><pre style="white-space:pre-wrap;background:#020617;padding:12px;border-radius:10px;">{html.escape(body)}</pre>
</body></html>"""


def inject_recovery_controls(page: str) -> str:
    card = """
<div class="card">
<h2>Emergency Draft Recovery</h2>
<form method="post" action="/action">
  <button class="no" name="action" value="clear_bugged">CLEAR BUGGED DRAFT</button>
  <button class="growth" name="action" value="generate_new">GENERATE NEW DRAFT</button>
  <button class="reconcile" name="action" value="refresh">REFRESH LIVE</button>
</form>
<p><strong>Use CLEAR BUGGED DRAFT for stale/generic drafts. Use GENERATE NEW DRAFT when the approval target is empty.</strong></p>
</div>
"""
    if "Emergency Draft Recovery" in page:
        return page
    if "<body>" in page:
        return page.replace("<body>", "<body>" + card, 1)
    return card + page


def inject_result(page: str, title: str, output: str) -> str:
    card = f"""
<div class="card">
<h2>{html.escape(title)}</h2>
<pre>{html.escape(output[-8000:])}</pre>
</div>
"""
    if "<body>" in page:
        return page.replace("<body>", "<body>" + card, 1)
    return card + page


def rebuild_dashboard() -> str:
    run_cmd(["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--write", "--format", "markdown"], timeout=45)
    code, out = run_cmd(["python3", "link_self_learning_dashboard.py", "render", "--format", "html", "--write"], timeout=90)
    if code != 0:
        return inject_recovery_controls(error_page("Dashboard render failed", out))
    if DASHBOARD_HTML.exists():
        return inject_recovery_controls(DASHBOARD_HTML.read_text(encoding="utf-8"))
    return inject_recovery_controls(out)


def handle_action(fields: dict[str, list[str]]) -> str:
    action = (fields.get("action") or ["refresh"])[0]
    draft_id = (fields.get("draft_id") or [""])[0].strip()
    feedback = (fields.get("feedback") or [""])[0].strip()
    outputs: list[str] = []

    if action in {"yes", "no", "try_again"}:
        if not draft_id:
            outputs.append("No draft_id supplied; decision skipped.")
        else:
            if not feedback:
                feedback = {
                    "yes": "Approved from dashboard.",
                    "no": "Rejected from dashboard.",
                    "try_again": "Try again with Brandon feedback.",
                }[action]
            code, out = run_cmd([
                "python3", "link_approval_patch_draft_queue.py", "decide",
                "--action", action,
                "--draft-id", draft_id,
                "--feedback", feedback,
                "--format", "markdown",
            ], timeout=60)
            outputs.append(f"$ decide {action} {draft_id}\nexit={code}\n{out}")
            code, out = run_cmd(["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--force-new", "--write", "--format", "markdown"], timeout=60)
            outputs.append(f"$ refill after decision\nexit={code}\n{out}")

    elif action == "clear_bugged":
        code, out = run_cmd(["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--write", "--format", "markdown"], timeout=60)
        outputs.append(f"$ clear bugged drafts\nexit={code}\n{out}")

    elif action in {"generate_new", "find_growth"}:
        code, out = run_cmd(["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--force-new", "--write", "--format", "markdown"], timeout=60)
        outputs.append(f"$ generate new draft\nexit={code}\n{out}")

    elif action == "run_tick":
        code, out = run_cmd(["python3", "link_autonomous_tick_runner.py", "--format", "markdown", "--write"], timeout=120)
        outputs.append(f"$ run tick\nexit={code}\n{out}")
        code, out = run_cmd(["python3", "link_dashboard_proposal_refill.py", "--clear-bugged", "--force-new", "--write", "--format", "markdown"], timeout=60)
        outputs.append(f"$ refill after tick\nexit={code}\n{out}")

    else:
        outputs.append("Live refresh.")

    return inject_result(rebuild_dashboard(), f"Action Result: {action}", "\n\n".join(outputs))


class Handler(BaseHTTPRequestHandler):
    def send_html(self, page: str) -> None:
        payload = page.encode("utf-8", "replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self.send_html(rebuild_dashboard())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", "replace")
        self.send_html(handle_action(urllib.parse.parse_qs(raw, keep_blank_values=True)))

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - - {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    if args.smoke:
        page = rebuild_dashboard()
        assert "Link Self-Learning Dashboard" in page
        assert "Emergency Draft Recovery" in page
        print("self-learning dashboard web admin smoke OK")
        return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving Link self-learning dashboard at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
