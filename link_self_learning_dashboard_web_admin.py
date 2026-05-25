#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DASHBOARD_HTML = ROOT / ".link/dashboard/self_learning_dashboard.html"


def run_cmd(args: list[str], timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    return p.returncode, p.stdout


def rebuild_dashboard() -> str:
    """
    Canonical live render path:
    1. Refill proposal only if pending is empty.
    2. Re-render dashboard HTML from current disk state.
    3. Return fresh HTML, never stale snapshot.
    """
    logs: list[str] = []

    code, out = run_cmd(
        ["python3", "link_dashboard_proposal_refill.py", "--write", "--format", "markdown"],
        timeout=60,
    )
    logs.append(f"refill exit={code}\n{out[-4000:]}")

    code, out = run_cmd(
        ["python3", "link_self_learning_dashboard.py", "render", "--format", "html", "--write"],
        timeout=60,
    )
    logs.append(f"render exit={code}\n{out[-4000:]}")

    if DASHBOARD_HTML.exists():
        body = DASHBOARD_HTML.read_text(encoding="utf-8")
    else:
        body = "<h1>Dashboard render failed</h1>"

    # Add visible server-side freshness marker.
    marker = f"""
<div class="card">
<h2>Live Web Server Marker</h2>
<p><strong>Served fresh:</strong> {html.escape(time.strftime('%Y-%m-%d %H:%M:%S'))}</p>
<p><strong>Server behavior:</strong> refill → render → serve, no cached snapshot.</p>
</div>
"""
    body = body.replace("</body>", marker + "\n</body>") if "</body>" in body else body + marker
    return body


def decide_or_action(form: dict[str, list[str]]) -> str:
    action = (form.get("action", ["refresh"])[0] or "refresh").strip()
    draft_id = (form.get("draft_id", ["latest"])[0] or "latest").strip()
    feedback = (form.get("feedback", [""])[0] or "").strip()

    if not feedback:
        feedback = f"{action} from dashboard."

    logs: list[str] = []

    if action in {"yes", "no", "try_again"}:
        cmd = [
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
        ]
        code, out = run_cmd(cmd, timeout=60)
        logs.append(f"decision exit={code}\n{out[-4000:]}")

    elif action == "run_tick":
        code, out = run_cmd(
            ["python3", "link_autonomous_tick_runner.py", "--format", "markdown"],
            timeout=120,
        )
        logs.append(f"tick exit={code}\n{out[-4000:]}")

    elif action == "find_growth":
        code, out = run_cmd(
            [
                "python3",
                "link_autonomous_growth_receipt.py",
                "--goal",
                "Find next concrete Link growth work",
                "--format",
                "markdown",
                "--write",
            ],
            timeout=120,
        )
        logs.append(f"growth exit={code}\n{out[-4000:]}")

    elif action == "reconcile":
        code, out = run_cmd(
            ["python3", "link_dashboard_proposal_refill.py", "--write", "--format", "markdown"],
            timeout=60,
        )
        logs.append(f"reconcile/refill exit={code}\n{out[-4000:]}")

    else:
        logs.append("refresh only")

    # Critical: after every action, immediately refill/render fresh.
    body = rebuild_dashboard()

    result = "<div class='card'><h2>Last Web Action Result</h2><pre>" + html.escape("\n\n".join(logs)) + "</pre></div>"
    body = body.replace("</body>", result + "\n</body>") if "</body>" in body else result + body
    return body


class Handler(BaseHTTPRequestHandler):
    def send_fresh_html(self, body: str, status: int = 200) -> None:
        raw = body.encode("utf-8", "replace")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        try:
            self.send_fresh_html(rebuild_dashboard())
        except Exception as e:
            self.send_fresh_html(f"<h1>GET failed</h1><pre>{html.escape(repr(e))}</pre>", 500)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", "replace")
            form = urllib.parse.parse_qs(raw)
            self.send_fresh_html(decide_or_action(form))
        except Exception as e:
            self.send_fresh_html(f"<h1>POST failed</h1><pre>{html.escape(repr(e))}</pre>", 500)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--serve", action="store_true", help="compatibility no-op")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    if args.smoke:
        body = rebuild_dashboard()
        assert "Link Self-Learning Dashboard" in body
        print("self-learning dashboard web admin smoke OK")
        return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving Link self-learning dashboard at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
