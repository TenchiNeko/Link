#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SELF_LEARNING_DASHBOARD_WEB_ADMIN_VERSION = "LU109-self-learning-dashboard-web-admin-v1"


STYLE = """
body {
  margin: 24px;
  font-family: Arial, sans-serif;
  background: #0f172a;
  color: #e5e7eb;
}
a { color: #93c5fd; }
.card {
  border: 1px solid #334155;
  border-radius: 14px;
  padding: 16px;
  margin: 14px 0;
  background: #111827;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
button {
  border: 0;
  border-radius: 10px;
  padding: 12px 16px;
  font-weight: 700;
  cursor: pointer;
}
.yes { background: #22c55e; color: #052e16; }
.no { background: #ef4444; color: #450a0a; }
.retry { background: #f59e0b; color: #451a03; }
.tick { background: #60a5fa; color: #082f49; }
.loop { background: #a78bfa; color: #2e1065; }
.growth { background: #34d399; color: #064e3b; }
.reconcile { background: #facc15; color: #422006; }
.refresh { background: #e5e7eb; color: #111827; }
textarea {
  width: 100%;
  min-height: 80px;
  border-radius: 10px;
  padding: 10px;
  background: #020617;
  color: #e5e7eb;
  border: 1px solid #334155;
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
  background: #020617;
  color: #e5e7eb;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 14px;
}
.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 999px;
  background: #1e293b;
  border: 1px solid #334155;
  margin-right: 6px;
}
.small { color: #94a3b8; font-size: 0.92em; }
"""


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run(cmd: list[str], root: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, (p.stdout or "").strip()
    except Exception as exc:
        return 99, str(exc)


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest_json(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None


def count_files(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len(list(folder.glob("*.json")))


def queue_counts(root: Path) -> dict[str, int]:
    agent = root / ".link" / "agent_queue"
    drafts = root / ".link" / "patch_drafts"
    return {
        "agent_pending": count_files(agent / "pending"),
        "agent_running": count_files(agent / "running"),
        "agent_done": count_files(agent / "done"),
        "agent_blocked": count_files(agent / "blocked"),
        "agent_receipts": count_files(agent / "receipts"),
        "draft_pending": count_files(drafts / "pending"),
        "draft_approved": count_files(drafts / "approved"),
        "draft_rejected": count_files(drafts / "rejected"),
        "draft_retry": count_files(drafts / "retry"),
        "draft_receipts": count_files(drafts / "receipts"),
    }


def is_stale_lu107_draft(path: Path, data: dict[str, Any]) -> bool:
    text = (path.name + "\n" + json.dumps(data, sort_keys=True)).lower()
    return "lu107" in text and "approval-gated patch draft" in text


def safe_target(path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if not target.exists():
        return target
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return target_dir / f"{path.stem}-{stamp}{path.suffix}"


def reconcile_stale_drafts(root: Path) -> dict[str, Any]:
    pending = root / ".link" / "patch_drafts" / "pending"
    rejected = root / ".link" / "patch_drafts" / "rejected"
    moved: list[str] = []

    if not pending.exists():
        return {"status": "ok", "moved": moved, "message": "No pending draft folder."}

    for path in sorted(pending.glob("*.json")):
        data = load_json(path)
        if not is_stale_lu107_draft(path, data):
            continue

        data["status"] = "stale_reconciled"
        data["reconciled_at"] = now()
        data["reconcile_reason"] = "LU107 was already completed; stale pending approval draft moved aside by LU109 dashboard route."

        target = safe_target(path, rejected)
        target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        path.unlink()
        moved.append(str(target))

        md = path.with_suffix(".md")
        if md.exists():
            md_target = target.with_suffix(".md")
            md_target.write_text(md.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            md.unlink()
            moved.append(str(md_target))

    return {
        "status": "ok",
        "moved": moved,
        "message": f"Moved {len(moved)} stale draft file(s)." if moved else "No stale LU107 drafts found.",
    }


def dashboard_markdown(root: Path) -> tuple[int, str]:
    return run(
        [sys.executable, "link_self_learning_dashboard.py", "--write", "--format", "markdown"],
        root,
        timeout=90,
    )


def decide(root: Path, action: str, feedback: str) -> dict[str, Any]:
    rec = reconcile_stale_drafts(root)
    pending = latest_json(root / ".link" / "patch_drafts" / "pending")
    if pending is None:
        return {
            "status": "no_action",
            "action": action,
            "output": "No actionable pending draft is waiting for approval.",
            "reconcile": rec,
        }

    feedback = feedback.strip() or f"{action} from LU109 live dashboard."
    rc, out = run(
        [
            sys.executable,
            "link_approval_patch_draft_queue.py",
            "decide",
            "--action",
            action,
            "--draft-id",
            "latest",
            "--feedback",
            feedback,
            "--format",
            "markdown",
        ],
        root,
        timeout=90,
    )
    return {"status": "ok" if rc == 0 else "failed", "action": action, "exit": rc, "output": out, "reconcile": rec}


def run_one_tick(root: Path) -> dict[str, Any]:
    rc, out = run([sys.executable, "link_autonomous_tick_runner.py", "--write", "--format", "markdown"], root, timeout=120)
    return {"status": "ok" if rc == 0 else "failed", "action": "run_tick", "exit": rc, "output": out}


def find_growth(root: Path) -> dict[str, Any]:
    rc, out = run(
        [
            sys.executable,
            "link_autonomous_growth_receipt.py",
            "--goal",
            "Find next autonomous Link growth work",
            "--format",
            "markdown",
            "--write",
        ],
        root,
        timeout=120,
    )
    return {"status": "ok" if rc == 0 else "failed", "action": "find_growth", "exit": rc, "output": out}


def run_loop(root: Path, max_ticks: int = 10) -> dict[str, Any]:
    max_ticks = max(1, min(max_ticks, 25))
    outputs: list[str] = []
    stop_reason = "max_ticks"

    for index in range(max_ticks):
        counts_before = queue_counts(root)
        if counts_before["draft_pending"] > 0:
            stop_reason = "waiting_approval"
            break
        if counts_before["agent_pending"] == 0:
            stop_reason = "nothing_pending"
            break

        result = run_one_tick(root)
        outputs.append(f"## Tick {index + 1}\n\n{result.get('output', '')}")

        counts_after = queue_counts(root)
        if counts_after["draft_pending"] > 0:
            stop_reason = "waiting_approval"
            break
        if counts_after["agent_pending"] == 0:
            stop_reason = "nothing_pending"
            break

    return {
        "status": "ok",
        "action": "run_loop",
        "stop_reason": stop_reason,
        "output": "\n\n".join(outputs) if outputs else f"Loop stopped immediately: {stop_reason}",
    }


def dispatch(root: Path, action: str, form: dict[str, str]) -> dict[str, Any]:
    feedback = form.get("feedback", "")
    if action in {"yes", "no", "try_again"}:
        return decide(root, action, feedback)
    if action == "run_tick":
        return run_one_tick(root)
    if action == "run_loop":
        ticks_raw = form.get("ticks", "10")
        try:
            ticks = int(ticks_raw)
        except ValueError:
            ticks = 10
        return run_loop(root, max_ticks=ticks)
    if action == "find_growth":
        return find_growth(root)
    if action == "reconcile":
        return {"status": "ok", "action": "reconcile", "output": json.dumps(reconcile_stale_drafts(root), indent=2)}
    if action == "refresh":
        return {"status": "ok", "action": "refresh", "output": "Dashboard refreshed."}
    return {"status": "denied", "action": action, "output": f"Unknown action denied: {action}"}


def result_block(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    pretty = json.dumps(result, indent=2, sort_keys=True)
    output = result.get("output")
    if output:
        pretty = f"{pretty}\n\n--- action output ---\n{output}"
    return f"""
    <div class="card">
      <h2>Last Action Result</h2>
      <pre>{html.escape(pretty)}</pre>
    </div>
    """


def render_page(root: Path, result: dict[str, Any] | None = None) -> str:
    rc, dash = dashboard_markdown(root)
    counts = queue_counts(root)
    mode = "waiting approval" if counts["draft_pending"] else "ready / no approval draft pending"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Link Self-Learning Dashboard</title>
<style>{STYLE}</style>
</head>
<body>
  <h1>Link Self-Learning Dashboard</h1>
  <p class="small">
    Version: <code>{SELF_LEARNING_DASHBOARD_WEB_ADMIN_VERSION}</code> · Generated: {html.escape(now())}
  </p>

  <div class="card">
    <span class="badge">Mode: {html.escape(mode)}</span>
    <span class="badge">Agent pending: {counts["agent_pending"]}</span>
    <span class="badge">Draft pending: {counts["draft_pending"]}</span>
    <span class="badge">Receipts: {counts["agent_receipts"] + counts["draft_receipts"]}</span>
  </div>

  <div class="card">
    <h2>Feedback</h2>
    <form method="post">
      <textarea name="feedback" placeholder="Optional feedback for YES / NO / TRY AGAIN. Example: Try again but make it smaller and safer."></textarea>
      <div class="row" style="margin-top: 12px;">
        <button class="yes" name="action" value="yes">YES</button>
        <button class="no" name="action" value="no">NO</button>
        <button class="retry" name="action" value="try_again">TRY AGAIN</button>
        <button class="tick" name="action" value="run_tick">RUN ONE TICK</button>
        <button class="loop" name="action" value="run_loop">RUN LOOP</button>
        <button class="growth" name="action" value="find_growth">FIND GROWTH WORK</button>
        <button class="reconcile" name="action" value="reconcile">RECONCILE STALE DRAFTS</button>
        <button class="refresh" name="action" value="refresh">REFRESH</button>
      </div>
      <p class="small">Loop ticks: <input name="ticks" value="10" style="width:60px;"> Stops when approval is needed, no work is pending, or max ticks is reached.</p>
    </form>
  </div>

  {result_block(result)}

  <div class="card">
    <h2>Dashboard Receipt</h2>
    <p class="small">Source command exit: {rc}</p>
    <pre>{html.escape(dash)}</pre>
  </div>

  <div class="card">
    <h2>Safety Boundary</h2>
    <ul>
      <li>Buttons can inspect queues, write local <code>.link</code> receipts, approve/reject drafts, and run safe tick/growth commands.</li>
      <li>Source edits, commits, pushes, destructive commands, and unknown external code remain approval-gated.</li>
      <li>The web server binds to <code>127.0.0.1</code> by default.</li>
    </ul>
  </div>
</body>
</html>
"""


def write_snapshot(root: Path) -> Path:
    out = root / ".link" / "dashboard" / "self_learning_dashboard_web_admin.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(root), encoding="utf-8")
    return out


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], handler: type[BaseHTTPRequestHandler], root: Path):
        super().__init__(addr, handler)
        self.root = root
        self.last_result: dict[str, Any] | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            payload = {
                "ok": True,
                "version": SELF_LEARNING_DASHBOARD_WEB_ADMIN_VERSION,
                "generated": now(),
                "counts": queue_counts(self.server.root),  # type: ignore[attr-defined]
            }
            self._send(200, json.dumps(payload, indent=2), "application/json; charset=utf-8")
            return

        self._send(200, render_page(self.server.root, self.server.last_result))  # type: ignore[attr-defined]

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        parsed = urllib.parse.parse_qs(raw)
        form = {k: v[-1] if v else "" for k, v in parsed.items()}
        action = form.get("action", "refresh")
        result = dispatch(self.server.root, action, form)  # type: ignore[attr-defined]
        self.server.last_result = result  # type: ignore[attr-defined]
        self._send(200, render_page(self.server.root, result))


def smoke(root: Path) -> None:
    page = render_page(root, {"status": "smoke", "output": "smoke"})
    required = [
        SELF_LEARNING_DASHBOARD_WEB_ADMIN_VERSION,
        "YES",
        "NO",
        "TRY AGAIN",
        "RUN ONE TICK",
        "RUN LOOP",
        "FIND GROWTH WORK",
        "Safety Boundary",
    ]
    missing = [item for item in required if item not in page]
    if missing:
        raise SystemExit(f"missing dashboard markers: {missing}")
    print("self-learning dashboard web admin smoke OK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--write-snapshot", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()

    if args.smoke:
        smoke(root)
        return 0

    if args.write_snapshot:
        path = write_snapshot(root)
        print(f"Written dashboard: `{path}`")
        return 0

    if args.serve:
        server = DashboardServer((args.host, args.port), Handler, root)
        url = f"http://{args.host}:{args.port}"
        print(f"Link self-learning dashboard running: {url}")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
        return 0

    print(render_page(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
