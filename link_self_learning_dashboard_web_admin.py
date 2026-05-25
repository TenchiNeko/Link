#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from link_self_learning_dashboard import build_dashboard, render_html


WEB_ADMIN_VERSION = "LU110-self-learning-dashboard-web-admin-approval-sync-v1"


def run(cmd: list[str], root: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except Exception as exc:
        return 99, str(exc)


def write_last_action(root: Path, payload: dict) -> None:
    path = root / ".link" / "dashboard" / "last_action.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reconcile_stale_drafts(root: Path) -> str:
    pending = root / ".link" / "patch_drafts" / "pending"
    retry = root / ".link" / "patch_drafts" / "retry"
    done = root / ".link" / "agent_queue" / "done"
    retry.mkdir(parents=True, exist_ok=True)

    done_text = "\n".join(p.name.lower() for p in done.glob("*.json")) if done.exists() else ""
    moved = []
    for path in sorted(pending.glob("*.json")) if pending.exists() else []:
        data = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        task_id = str(data.get("task_id") or data.get("id") or "").lower()
        if task_id and task_id in done_text:
            data["status"] = "retry"
            data["reconcile_reason"] = f"Pending draft was stale because task {task_id} is already done."
            target = retry / path.name
            target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            path.unlink()
            moved.append(str(target))
    return "No stale drafts moved." if not moved else "Moved stale drafts:\n" + "\n".join(moved)


class Handler(BaseHTTPRequestHandler):
    root: Path = Path.cwd()

    def do_GET(self) -> None:
        dashboard = build_dashboard(self.root, run_healthcheck=False)
        body = render_html(dashboard).replace(
            "<p>Version:",
            f"<p>Web admin: <code>{WEB_ADMIN_VERSION}</code> · Version:",
            1,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw)
        action = (form.get("action") or ["refresh"])[0]
        feedback = (form.get("feedback") or [""])[0]
        draft_id = (form.get("draft_id") or ["latest"])[0] or "latest"

        if action in {"yes", "no", "try_again"}:
            code, out = run([
                "python3", "link_approval_patch_draft_queue.py", "decide",
                "--action", action,
                "--draft-id", draft_id,
                "--feedback", feedback or f"{action} from dashboard.",
                "--format", "markdown",
            ], self.root)
        elif action == "run_tick":
            code, out = run(["python3", "link_autonomous_tick_runner.py", "--write", "--format", "markdown"], self.root)
        elif action == "find_growth":
            code, out = run([
                "python3", "link_autonomous_growth_receipt.py",
                "--goal", "Find next autonomous Link growth work",
                "--format", "markdown",
                "--write",
            ], self.root)
        elif action == "reconcile":
            code, out = 0, reconcile_stale_drafts(self.root)
        else:
            code, out = 0, "Refreshed."

        write_last_action(self.root, {
            "action": action,
            "draft_id": draft_id,
            "feedback": feedback,
            "exit": code,
            "output": out[-8000:],
        })

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run dashboard web-admin smoke check and exit.")
    parser.add_argument("--serve", action="store_true", help="Compatibility no-op; serving is the default mode.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()


    if getattr(args, "smoke", False):
        from pathlib import Path as _Path
        from link_self_learning_dashboard import build_dashboard, render_html

        data = build_dashboard(root=_Path(args.root), include_healthcheck=False)
        page = render_html(data)

        assert "Link Self-Learning Dashboard" in page
        assert "Approval Controls" in page
        assert "YES" in page
        assert "NO" in page
        assert "TRY AGAIN" in page
        assert "Approval Target" in page

        print("self-learning dashboard web admin smoke OK")
        return

    Handler.root = Path(args.root).resolve()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving Link self-learning dashboard at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
