#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import inspect
import json
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Any

VERSION = "LU240-link-factory-job-bridge-v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def queue_root(root: Path) -> Path:
    return root / ".link" / "agent_queue"


def safe_read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"status": "blocked", "error": str(exc), "path": str(path)}


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def pending_jobs(root: Path) -> list[Path]:
    pending = queue_root(root) / "pending"
    if not pending.exists():
        return []
    return sorted(pending.glob("*.json"))


def select_job(root: Path, task_id: str | None = None) -> tuple[Path | None, dict[str, Any] | None]:
    jobs = pending_jobs(root)
    if not jobs:
        return None, None

    if task_id:
        wanted = task_id.lower()
        for path in jobs:
            data = safe_read_json(path)
            if wanted == str(data.get("task_id", "")).lower() or wanted in path.name.lower():
                return path, data
        return None, None

    path = jobs[0]
    return path, safe_read_json(path)


def job_goal(data: dict[str, Any]) -> str:
    task_id = str(data.get("task_id") or "").strip()
    title = str(data.get("title") or "").strip()
    why = str(data.get("why") or "").strip()
    source_draft = str(data.get("source_draft_path") or data.get("source_draft_id") or "").strip()

    lines = [
        f"Implement {task_id} {title}".strip(),
        "",
        "This is a Link approved implementation job. Produce a concrete implementation plan or patch-ready output for the listed files.",
    ]

    if why:
        lines += ["", "Why:", why]

    if source_draft:
        lines += ["", f"Source draft: {source_draft}"]

    files = data.get("files") or []
    if files:
        lines += ["", "Target files:"]
        lines += [f"- {x}" for x in files]

    plan = data.get("plan") or []
    if plan:
        lines += ["", "Approved plan:"]
        lines += [f"- {x}" for x in plan]

    tests = data.get("tests") or []
    if tests:
        lines += ["", "Expected verification:"]
        lines += [f"- {x}" for x in tests]

    lines += [
        "",
        "Factory requirements:",
        "- Do not touch unrelated research/reference material.",
        "- Preserve approval receipt evidence and rollback safety.",
        "- Return concrete file-level implementation guidance, risks, and verification steps.",
        "- If model execution is enabled, generate useful role outputs under factory/projects/.",
    ]

    return "\n".join(lines).strip()


def run_factory_pipeline(
    *,
    root: Path,
    project: str,
    goal: str,
    tier: str,
    execute_models: bool,
    max_tokens: int,
) -> dict[str, Any]:
    import sys

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from factory.factory_pipeline import run_pipeline  # type: ignore

    kwargs = {
        "project": project,
        "goal": goal,
        "tier": tier,
        "execute_models": execute_models,
        "max_tokens": max_tokens,
    }

    sig = inspect.signature(run_pipeline)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}

    try:
        result = run_pipeline(**accepted)
    except TypeError:
        # Compatibility fallback for older positional signatures.
        result = run_pipeline(project, goal, tier, execute_models)

    return result if isinstance(result, dict) else {"result": result}


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Link Factory Job Bridge Receipt",
        "",
        f"Version: `{receipt.get('version')}`",
        f"Generated: `{receipt.get('generated_at')}`",
        f"Status: **{receipt.get('status')}**",
        f"Project: `{receipt.get('project')}`",
        f"Tier: `{receipt.get('tier')}`",
        f"Execute models: **{receipt.get('execute_models')}**",
        f"Mark done: **{receipt.get('mark_done')}**",
        "",
    ]

    task = receipt.get("task") or {}
    if task:
        lines += [
            "## Task",
            "",
            f"- ID: `{task.get('task_id')}`",
            f"- Title: **{task.get('title')}**",
            f"- Source: `{task.get('source_path')}`",
            "",
        ]

    factory_result = receipt.get("factory_result") or {}
    if factory_result:
        lines += ["## Factory Result", ""]
        for key in ["run_dir", "manifest", "summary", "roles", "execute_models"]:
            if key in factory_result:
                lines.append(f"- {key}: `{factory_result.get(key)}`")
        lines.append("")

    if receipt.get("moved_to"):
        lines += [f"Moved to done: `{receipt.get('moved_to')}`", ""]

    if receipt.get("error"):
        lines += [
            "## Error",
            "",
            "```",
            str(receipt.get("error")),
            "```",
            "",
        ]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the next Link agent queue job through the existing factory pipeline.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--project", default="link_upgrade_research")
    parser.add_argument("--tier", default="cheap")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--execute-models", action="store_true")
    parser.add_argument("--mark-done", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=6500)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source_path, data = select_job(root, args.task_id)

    receipt: dict[str, Any] = {
        "version": VERSION,
        "generated_at": utc_now(),
        "repo": str(root),
        "project": args.project,
        "tier": args.tier,
        "execute_models": bool(args.execute_models),
        "mark_done": bool(args.mark_done),
        "status": "unknown",
    }

    if source_path is None or data is None:
        receipt["status"] = "no_pending_job"
        receipt["reason"] = "No pending Link agent queue job matched the request."
    else:
        task_id = str(data.get("task_id") or source_path.stem)
        receipt["task"] = {
            "task_id": task_id,
            "title": data.get("title"),
            "source_path": str(source_path),
            "status": data.get("status"),
            "risk": data.get("risk"),
        }

        try:
            goal = job_goal(data)
            receipt["goal"] = goal
            result = run_factory_pipeline(
                root=root,
                project=args.project,
                goal=goal,
                tier=args.tier,
                execute_models=bool(args.execute_models),
                max_tokens=int(args.max_tokens),
            )
            receipt["factory_result"] = result
            receipt["status"] = "success"

            if args.mark_done:
                done_dir = queue_root(root) / "done"
                done_dir.mkdir(parents=True, exist_ok=True)
                done_path = done_dir / source_path.name

                data["status"] = "done_factory_run"
                data["completed_at"] = utc_now()
                data["factory_bridge_receipt_version"] = VERSION
                data["factory_result"] = result

                atomic_write_json(done_path, data)
                source_path.unlink()
                receipt["moved_to"] = str(done_path)

        except Exception as exc:
            receipt["status"] = "failed"
            receipt["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"

    receipts = queue_root(root) / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    task_part = ((receipt.get("task") or {}).get("task_id") or "none").lower()
    receipt_path = receipts / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-factory-{task_part}.json"
    atomic_write_json(receipt_path, receipt)
    receipt["written_path"] = str(receipt_path)

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(render_markdown(receipt))

    return 0 if receipt["status"] in {"success", "no_pending_job"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
