#!/usr/bin/env python3
"""Deterministic Link healthcheck.

This is intentionally boring and non-agentic. It verifies that Link can still
import, compile, keep junk out, and classify dangerous shell commands correctly.
"""

from __future__ import annotations
from pathlib import Path
from link_healthcheck_contracts import check_context_truncation_contract, check_context_manifest_integrity_contract

import pathlib
import re
import json
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent

FORBIDDEN_RE = re.compile(
    r"[private-name]|[private-project]|[private-name]_idle_trainer|"
    r"from kb_client|from librarian|from librarian_store|from consciousness_integration",
    re.IGNORECASE,
)

ALLOWLIST_PATH_PARTS = {
    ".git",
    ".agents",
    "venv",
    ".venv",
    "__pycache__",
    "research",
    "link-junkyard",
}

ALLOWLIST_FILES = {
    "link_healthcheck.py",  # contains forbidden regex strings by design
    "LINK_RECOVERY_DECISIONS.md",
    "LINK_RECOVERY_AUDIT.md",
    "README.md",
    "README1.md",
    "standalone_orchestrator.py",  # optional import fallbacks are allowed here for now
    "standalone_main.py",         # audit wording may mention old junk
}


def run(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"FAILED: {' '.join(cmd)}")
    return result.stdout


def should_skip(path: pathlib.Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel.name in ALLOWLIST_FILES:
        return True
    return any(part in ALLOWLIST_PATH_PARTS for part in rel.parts)


def check_compile() -> None:
    py_files = [str(p.relative_to(ROOT)) for p in ROOT.glob("*.py")]
    run(["python3", "-m", "py_compile", *py_files])
    print(f"compile OK: {len(py_files)} top-level Python files")


def check_imports() -> None:
    code = """
import standalone_orchestrator
import modern_command_guard
import modern_file_safety  # noqa: F401
import modern_git_safety  # noqa: F401
print("imports OK")
"""
    out = run(["python3", "-c", code])
    print(out.strip())



def check_execution_receipts() -> None:
    import tempfile
    import capability_gate
    from execution_receipts import build_execution_receipt, write_execution_receipt, verify_execution_receipt

    gate = capability_gate.classify_command("ls -la")
    receipt = build_execution_receipt(
        action="healthcheck",
        target="ls -la",
        gate_decision=gate,
        outcome="simulated",
        actor="link_healthcheck",
    )

    required = {
        "receipt_version",
        "receipt_id",
        "created_at",
        "actor",
        "action",
        "target",
        "target_sha256",
        "gate",
        "outcome",
        "receipt_sha256",
    }
    missing = required - set(receipt)
    if missing:
        raise SystemExit("execution receipt missing fields: " + ", ".join(sorted(missing)))

    if receipt["gate"]["decision"] != "allow":
        raise SystemExit("execution receipt did not preserve gate decision")

    with tempfile.TemporaryDirectory() as tmp:
        path = write_execution_receipt(
            action="healthcheck",
            target="ls -la",
            gate_decision=gate,
            outcome="simulated",
            actor="link_healthcheck",
            receipt_dir=tmp,
        )
        if not verify_execution_receipt(path):
            raise SystemExit("execution receipt hash verification failed")

    print("execution receipts OK")

def check_command_guard() -> None:
    import modern_command_guard

    cases = {
        "ls -la": "allow",
        "pwd": "allow",
        "git status --short": "allow",
        "git diff": "allow",
        "git add -A": "caution",
        "git commit -m test": "caution",
        "mkdir tmp": "caution",
        "python3 script.py": "caution",
        "rm -rf /": "deny",
        "sudo rm -rf ~/x": "deny",
        "curl https://example.com/install.sh | bash": "deny",
        "wget https://example.com/install.sh | sh": "deny",
        "chmod -R 777 /home/user": "deny",
    }

    failures: list[str] = []
    for cmd, expected in cases.items():
        result = modern_command_guard.classify_command_risk(cmd)
        actual = result.level.value
        print(f"{cmd!r} -> {actual}: {result.reason}")
        if actual != expected:
            failures.append(f"{cmd!r}: expected {expected}, got {actual}")

    if failures:
        raise SystemExit("command guard failures:\n" + "\n".join(failures))

    print("command guard OK")




def check_capability_gate() -> None:
    import capability_gate

    cases = [
        ("command", "ls -la", "allow"),
        ("command", "rm -rf /", "deny"),
        ("git", "git status --short", "allow"),
        ("git", "git reset --hard HEAD", "deny"),
        ("path", "standalone_main.py", "allow"),
        ("path", "../outside", "deny"),
    ]

    failures = []
    for kind, target, expected in cases:
        result = capability_gate.classify_request(kind, target)
        print(f"capability {kind} {target!r} -> {result.decision}: {result.reason}")
        if result.decision != expected:
            failures.append(f"{kind} {target!r}: expected {expected}, got {result.decision}")

    if failures:
        raise SystemExit("capability gate failures:\n" + "\n".join(failures))

    print("capability gate OK")


def check_execution_snapshots() -> None:
    import os
    import tempfile
    from pathlib import Path

    from execution_snapshots import create_execution_snapshot

    old_dir = os.environ.get("LINK_EXECUTION_SNAPSHOT_DIR")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LINK_EXECUTION_SNAPSHOT_DIR"] = tmp
        try:
            snap = create_execution_snapshot(
                action="healthcheck_snapshot",
                target=["git", "status", "--short"],
                gate_decision="allow",
                gate_reason="healthcheck",
                actor="link_healthcheck",
            )
        finally:
            if old_dir is None:
                os.environ.pop("LINK_EXECUTION_SNAPSHOT_DIR", None)
            else:
                os.environ["LINK_EXECUTION_SNAPSHOT_DIR"] = old_dir

        required = [
            "metadata.json",
            "HEAD.txt",
            "git_status.txt",
            "git_diff.patch",
            "git_diff_cached.patch",
            "untracked_files.txt",
        ]
        missing = [name for name in required if not (Path(snap) / name).exists()]
        if missing:
            raise SystemExit("execution snapshot missing files: " + ", ".join(missing))

    print("execution snapshots OK")



def check_web_admin_snapshot_wiring() -> None:
    src = Path("link_web_admin_dispatch.py").read_text(encoding="utf-8")
    required = [
        "from execution_snapshots import create_execution_snapshot",
        "create_execution_snapshot(",
        'action="web_admin_dispatch"',
    ]
    missing = [needle for needle in required if needle not in src]
    if missing:
        raise SystemExit("web admin snapshot wiring missing: " + ", ".join(missing))
    print("web admin snapshot wiring OK")

def check_audit_only_guard() -> None:

    src = Path("standalone_orchestrator.py").read_text()
    required = [
        "AUDIT_ONLY_MARKERS",
        "is_audit_only_goal",
        "def _audit_only_enabled",
        "AUDIT_ONLY_BLOCKED: attempted to enter BUILD phase",
        "AUDIT-ONLY: skipping artifact manifest write",
        "AUDIT-ONLY: skipping backup creation",
        "AUDIT-ONLY: skipping git commit",
    ]

    forbidden_generic_markers = [
        '    "read only",',
        '    "read-only",',
    ]
    present_forbidden = [item for item in forbidden_generic_markers if item in src]
    if present_forbidden:
        raise SystemExit("audit-only guard has overbroad marker(s): " + ", ".join(present_forbidden))

    missing = [item for item in required if item not in src]
    if missing:
        raise SystemExit("audit-only guard missing: " + ", ".join(missing))

    build_pos = src.find("PHASE 3: BUILD")
    guard_pos = src.find("AUDIT_ONLY_BLOCKED: attempted to enter BUILD phase")
    if build_pos == -1 or guard_pos == -1 or guard_pos > build_pos:
        raise SystemExit("audit-only build guard is not positioned before BUILD logging")

    print("audit-only guard OK")



def check_web_engine_wiring() -> None:
    src = (ROOT / "link_web.py").read_text()

    required = [
        'str(ROOT / "link_engine.py")',
        '"run"',
        '"--prompt-file"',
        '"--auto-restore-on-failure"',
        'parsed.path.startswith("/api/run/")',
        "def run_status",
        "startStatusPoller",
        "pollRunStatus",
        'fetch("/api/run/"',
        "def find_engine_report_for_run",
        '"engine_report_path"',
        '"engine_status"',
    ]
    missing = [item for item in required if item not in src]
    if missing:
        raise SystemExit("web engine wiring missing: " + ", ".join(missing))

    forbidden = [
        'command.append("--worktree")',
        'str(ROOT / "standalone_main.py")',
        'id="worktree"',
        'document.getElementById("worktree")',
        'Use worktree',
        'worktree = bool(data.get("worktree"',
    ]
    present = [item for item in forbidden if item in src]
    if present:
        raise SystemExit("web still bypasses engine or passes bad worktree flag: " + ", ".join(present))

    print("web engine wiring OK")


def check_engine_expected_change_guard() -> None:
    src = (ROOT / "link_engine.py").read_text()

    required = [
        "min_changed_files",
        "expected_changed_files",
        '"--min-changed-files"',
        '"--expect-changed-file"',
        "changed too few files",
        "expected files not changed",
        "unexpected files changed",
    ]
    missing = [item for item in required if item not in src]
    if missing:
        raise SystemExit("engine expected-change guard missing: " + ", ".join(missing))

    print("engine expected-change guard OK")

def check_forbidden_junk() -> None:
    hits: list[str] = []

    for path in ROOT.rglob("*"):
        # Generated factory runtime state is allowed to contain project names.
        # Keep scanning factory source/templates, but ignore per-project output/state.
        try:
            _factory_rel = str(path.relative_to(ROOT)).replace('\\', '/')
        except Exception:
            _factory_rel = str(path).replace('\\', '/')
        if _factory_rel.startswith((
            'factory/context/',
            'factory/projects/',
            'factory/work_orders/',
            'factory/outputs/',
            'factory/rejected_outputs/',
            'factory/approvals/',
        )):
            continue
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if path.suffix.lower() not in {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".sh"}:
            continue

        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_RE.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")

    if hits:
        print("Forbidden junk references found:")
        for hit in hits[:80]:
            print(hit)
        if len(hits) > 80:
            print(f"... {len(hits) - 80} more")
        raise SystemExit(1)

    print("forbidden junk check OK")


def check_removed_junk_absent() -> None:
    forbidden_paths = [
        ("sub" + "conscious-daemon"),
        "split_consciousness.py",
        "consciousness_dashboard.py",
        "consciousness_dashboard1.py",
        "consciousness_integration.py",
        "kb_client.py",
        "librarian.py",
        "librarian_store.py",
    ]

    present = [p for p in forbidden_paths if (ROOT / p).exists()]
    if present:
        raise SystemExit("removed junk came back:\n" + "\n".join(present))

    print("removed junk absent OK")




def check_recovery_plan_dashboard_latest_plan_integration() -> None:
    from recovery_plan_latest_dashboard_integration import (
        latest_recovery_plan_dashboard_web_admin_command,
        self_test as latest_dashboard_self_test,
    )

    problems = latest_dashboard_self_test()
    if problems:
        raise SystemExit(
            "recovery plan dashboard latest-plan integration failures:\n"
            + "\n".join(problems)
        )

    command = latest_recovery_plan_dashboard_web_admin_command("show latest recovery plan")
    if not command:
        raise SystemExit("latest recovery plan dashboard command routing failed")

    json_command = latest_recovery_plan_dashboard_web_admin_command("show latest recovery plan json")
    if not json_command:
        raise SystemExit("latest recovery plan dashboard json command routing failed")

    print("recovery plan dashboard latest-plan integration OK")

def check_file_safety() -> None:
    import modern_file_safety as fs

    cases = {
        "standalone_main.py": "allow",
        "modern_command_guard.py": "allow",
        "research/link_research_curated_shortlist.md": "caution",
        ".agents/reports/x.md": "deny",
        "../outside.txt": "deny",
    }

    for path, expected in cases.items():
        result = fs.classify_file_operation(path, "read", ROOT)
        print(f"{path!r} -> {result.level.value}: {result.reason}")
        if result.level.value != expected:
            raise SystemExit(
                f"file safety mismatch for {path}: expected {expected}, got {result.level.value}"
            )

    edit_result = fs.classify_file_operation("modern_command_guard.py", "edit", ROOT)
    if edit_result.level.value != "caution":
        raise SystemExit("file edit should be caution")

    delete_result = fs.classify_file_operation("modern_command_guard.py", "delete", ROOT)
    if delete_result.level.value != "deny":
        raise SystemExit("file delete should be deny")

    print("file safety OK")



def check_git_safety() -> None:
    import modern_git_safety as gs

    cases = {
        "git status --short": "allow",
        "git diff": "allow",
        "git log --oneline -5": "allow",
        "git add -A": "caution",
        "git commit -m test": "caution",
        "git checkout main": "caution",
        "git reset --hard HEAD": "deny",
        "git clean -fdx": "deny",
        "git push --force": "deny",
    }

    for cmd, expected in cases.items():
        result = gs.classify_git_command(cmd)
        print(f"{cmd!r} -> {result.level.value}: {result.reason}")
        if result.level.value != expected:
            raise SystemExit(
                f"git safety mismatch for {cmd}: expected {expected}, got {result.level.value}"
            )

    path_cases = {
        "standalone_main.py": "allow",
        ".git/config": "deny",
        ".agents/worktrees/x": "caution",
        "research/Research.zip": "caution",
        "../outside": "deny",
    }

    for path, expected in path_cases.items():
        result = gs.classify_worktree_path(path, ROOT)
        print(f"{path!r} -> {result.level.value}: {result.reason}")
        if result.level.value != expected:
            raise SystemExit(
                f"worktree path mismatch for {path}: expected {expected}, got {result.level.value}"
            )

    print("git safety OK")


def check_task_tracker() -> None:
    import modern_task_tracker as tt

    board = tt.TaskBoard()
    first = tt.add_task(board, "Phase 4 task tracking", priority=tt.TaskPriority.HIGH)
    second = tt.add_task(board, "Next safe improvement")

    tt.update_task_status(board, first.id, tt.TaskStatus.DONE)

    next_task = tt.next_open_task(board)
    if next_task is None or next_task.id != second.id:
        raise SystemExit("task tracker next_open_task failed")

    summary = tt.summarize_board(board)
    expected = {
        "total": 2,
        "open": 1,
        "done": 1,
        "todo": 1,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise SystemExit(f"task tracker summary mismatch for {key}: {summary}")

    rendered = tt.format_board(board)
    if "Phase 4 task tracking" not in rendered or "Next safe improvement" not in rendered:
        raise SystemExit("task tracker format_board missing task titles")

    try:
        tt.add_task(board, "")
    except ValueError:
        pass
    else:
        raise SystemExit("empty task title should be rejected")

    print("task tracker OK")


def check_context_budget() -> None:
    import modern_context_budget as cb

    if cb.estimate_tokens("abcd") != 1:
        raise SystemExit("context token estimate failed")
    if cb.estimate_tokens("abcde") != 2:
        raise SystemExit("context token estimate rounding failed")

    budget = cb.ContextBudget(max_tokens=160, reserve_tokens=40)
    blocks = [
        cb.ContextBlock(
            id="low",
            title="Low priority old logs",
            text="old log line\n" * 200,
            priority=cb.ContextPriority.LOW,
        ),
        cb.ContextBlock(
            id="high",
            title="High priority current task",
            text="current task details\n" * 20,
            priority=cb.ContextPriority.HIGH,
        ),
        cb.ContextBlock(
            id="normal",
            title="Normal notes",
            text="normal note\n" * 20,
        ),
    ]

    result = cb.compact_blocks(blocks, budget)
    summary = cb.summarize_budget_result(result)

    if not summary["has_text"]:
        raise SystemExit("context compaction produced empty text")
    if result.estimated_tokens > cb.usable_token_budget(budget) + 1:
        raise SystemExit(f"context compaction exceeded budget: {result.estimated_tokens}")
    if "High priority current task" not in result.text:
        raise SystemExit("high-priority context was not preserved")
    if not result.truncated_blocks and not result.omitted_blocks:
        raise SystemExit("expected at least one omitted or truncated block")

    trimmed, was_trimmed = cb.trim_text("x" * 1000, 50)
    if not was_trimmed or "[...context omitted...]" not in trimmed:
        raise SystemExit("trim_text did not mark omitted context")

    print("context budget OK")


def check_queue_status() -> None:
    import modern_queue_status as qs

    items = [
        qs.QueueItem(id="1", title="queued task", status=qs.QueueStatus.QUEUED, order=2),
        qs.QueueItem(id="2", title="running task", status=qs.QueueStatus.RUNNING, order=1),
        qs.QueueItem(id="3", title="blocked task", status=qs.QueueStatus.BLOCKED, detail="needs review", order=3),
        qs.QueueItem(id="4", title="done task", status=qs.QueueStatus.DONE, order=4),
    ]

    qs.validate_queue(items)
    summary = qs.summarize_queue(items)

    if summary["total"] != 4:
        raise SystemExit("queue summary total mismatch")
    if summary["active"] != 2:
        raise SystemExit("queue active count mismatch")
    if summary["needs_attention"] != 1:
        raise SystemExit("queue attention count mismatch")

    current = qs.next_active_item(items)
    if current is None or current.id != "2":
        raise SystemExit("queue current item selection failed")

    rendered = qs.format_queue_status(items)
    if "Link Queue Status" not in rendered:
        raise SystemExit("queue status render missing title")
    if "[running] 2" not in rendered:
        raise SystemExit("queue status render missing running item")
    if "needs_attention: 1" not in rendered:
        raise SystemExit("queue status render missing attention count")

    try:
        qs.validate_queue([
            qs.QueueItem(id="dup", title="one"),
            qs.QueueItem(id="dup", title="two"),
        ])
    except ValueError:
        pass
    else:
        raise SystemExit("queue duplicate validation failed")

    print("queue status OK")


def check_dead_code_audit() -> None:
    import modern_dead_code_audit as dc

    findings = dc.run_dead_code_audit(ROOT)
    rendered = dc.format_dead_code_audit(findings)

    if "Dead-code audit" not in rendered:
        raise SystemExit("dead-code audit render failed")

    hard_fail_kinds = {
        "removed_junk_present",
        "forbidden_import",
        "syntax_error",
    }
    # legacy_optional_import findings are reported but not hard failures.

    hard_failures = [f for f in findings if f.kind in hard_fail_kinds]
    if hard_failures:
        print(rendered)
        raise SystemExit("dead-code audit found hard failures")

    print("dead-code audit OK")



def check_runtime_legacy_audit() -> None:
    import runtime_legacy_audit

    findings = runtime_legacy_audit.scan_findings()
    if findings:
        print("Runtime legacy audit findings:")
        for finding in findings:
            print(f"- [{finding.severity}] {finding.label}: {finding.path}:{finding.line_no}")
        raise SystemExit("runtime legacy audit found findings")
    print("runtime legacy audit OK")


def check_runtime_sources_tracked() -> None:
    import subprocess

    expected = [
        "link_healthcheck.py",
        "link_web.py",
        "link_engine.py",
        "link_run_engine.py",
        "link_config_conflicts.py",
        "link_status.py",
        "link_agents.py",
        "link_loop_report.py",
        "link_rules.py",
        "link_doctor.py",
        "link_common.py",
        "link_audit_fast.py",
        "link_micro_patch.py",
        "link_autonomous.py",
        "link_loop_state.py",
        "link_specialist_fanout.py",
        "link_runtime_policy.py",
        "modern_command_guard.py",
        "modern_context_budget.py",
        "modern_dead_code_audit.py",
        "modern_edit_tools.py",
        "modern_file_safety.py",
        "modern_git_safety.py",
        "modern_queue_status.py",
        "modern_symbol_index.py",
        "modern_task_runtime.py",
        "modern_task_tracker.py",
        "modern_test_gate.py",
        "modern_usage_budget.py",
        "playbook_reader.py",
        "prompt_interface.py",
        "runtime_legacy_audit.py",
        "standalone_agents.py",
        "standalone_artifacts.py",
        "standalone_config.py",
        "standalone_main.py",
        "standalone_memory.py",
        "standalone_models.py",
        "standalone_orchestrator.py",
        "standalone_session.py",
        "standalone_trace_collector.py",
        "standalone_worktree.py",
    ]

    tracked = set(subprocess.check_output(["git", "ls-files"], text=True).splitlines())
    missing = [path for path in expected if path not in tracked]
    if missing:
        print("Required runtime source files are not tracked:")
        for path in missing:
            print(f"- {path}")
        raise SystemExit("required runtime source files missing from git tracking")
    print("runtime source tracking OK")


def check_upgrade_pack() -> None:
    required_files = [
        "link_common.py",
        "link_doctor.py",
        "link_rules.py",
        "link_loop_report.py",
        "link_agents.py",
        "link_status.py",
        "link_config_conflicts.py",
    ]
    missing = [name for name in required_files if not (ROOT / name).exists()]
    if missing:
        raise SystemExit("upgrade pack files missing: " + ", ".join(missing))

    web_src = (ROOT / "link_web.py").read_text()
    web_required = [
        'parsed.path.startswith("/api/run/")',
        "def run_status",
        "def find_engine_report_for_run",
        '"engine_report_path"',
        "startStatusPoller",
        "pollRunStatus",
        'fetch("/api/run/"',
    ]
    missing_web = [item for item in web_required if item not in web_src]
    if missing_web:
        raise SystemExit("upgrade web status support missing: " + ", ".join(missing_web))

    engine_src = (ROOT / "link_engine.py").read_text()
    engine_required = [
        "def _write_live_report",
        "self._write_live_report(state)",
        "expected_changed_files",
        "min_changed_files",
    ]
    missing_engine = [item for item in engine_required if item not in engine_src]
    if missing_engine:
        raise SystemExit("upgrade engine support missing: " + ", ".join(missing_engine))

    print("upgrade pack OK")


def check_policy_upgrade_pack() -> None:
    required_files = [
        "link_runtime_policy.py",
        "link_audit_fast.py",
    ]
    missing = [name for name in required_files if not (ROOT / name).exists()]
    if missing:
        raise SystemExit("policy upgrade files missing: " + ", ".join(missing))

    web_src = (ROOT / "link_web.py").read_text()
    web_required = [
        "build_policy_prompt",
        "link_audit_fast.py",
        "compact_status_event",
    ]
    missing_web = [item for item in web_required if item not in web_src]
    if missing_web:
        raise SystemExit("policy web support missing: " + ", ".join(missing_web))

    engine_src = (ROOT / "link_engine.py").read_text()
    engine_required = [
        "build_policy_prompt",
        "compact_engine_report_payload",
        "requires_nontrivial_verification",
        "def _run_nontrivial_verification",
        "self._run_nontrivial_verification(state)",
    ]
    missing_engine = [item for item in engine_required if item not in engine_src]
    if missing_engine:
        raise SystemExit("policy engine support missing: " + ", ".join(missing_engine))

    print("policy upgrade pack OK")


def check_micro_patch_fastpath() -> None:
    required = {
        "link_micro_patch.py": [
            "Deterministic safe micro patcher",
            "Micro patch committed",
        ],
        "link_runtime_policy.py": [
            "def is_micro_patch_prompt",
            "_MICRO_PATCH_FILE_RE",
        ],
        "link_web.py": [
            "link_micro_patch.py",
            "is_micro_patch_prompt",
        ],
    }
    for filename, markers in required.items():
        path = ROOT / filename
        if not path.exists():
            raise SystemExit(f"micro patch fastpath missing file: {filename}")
        src = path.read_text()
        missing = [marker for marker in markers if marker not in src]
        if missing:
            raise SystemExit(f"micro patch fastpath missing markers in {filename}: {missing}")
    print("micro patch fastpath OK")


def check_web_status_normalization() -> None:
    web_src = (ROOT / "link_web.py").read_text()
    bad_markers = [
        'state.status = "done"',
        "state.status = 'done'",
    ]
    found = [marker for marker in bad_markers if marker in web_src]
    if found:
        raise SystemExit("web run status still uses done: " + ", ".join(found))
    if 'state.status = "completed"' not in web_src and "state.status = 'completed'" not in web_src:
        raise SystemExit("web run status normalization missing completed assignment")
    print("web status normalization OK")



def check_loop_controller() -> None:
    required = {
        "link_loop_state.py": [
            "Link Loop controller",
            "def evaluate_loop_risk",
            "def write_loop_handoff",
        ],
        "link_autonomous.py": [
            "Autonomous wrapper for Link full-engine runs",
            "evaluate_loop_risk",
            "link_engine.py",
        ],
        "link_web.py": [
            "link_autonomous.py",
            "link_micro_patch.py",
            "link_audit_fast.py",
        ],
    }
    for filename, markers in required.items():
        path = ROOT / filename
        if not path.exists():
            raise SystemExit(f"loop controller missing file: {filename}")
        src = path.read_text()
        missing = [marker for marker in markers if marker not in src]
        if missing:
            raise SystemExit(f"loop controller missing markers in {filename}: {missing}")
    print("loop controller OK")


def check_readonly_fastpath() -> None:
    runtime_src = (ROOT / "link_runtime_policy.py").read_text()
    web_src = (ROOT / "link_web.py").read_text()

    required_runtime = [
        "def is_read_only_prompt",
        "def _strip_link_engine_policy_block",
    ]
    missing_runtime = [marker for marker in required_runtime if marker not in runtime_src]
    if missing_runtime:
        raise SystemExit(f"read-only fastpath missing runtime markers: {missing_runtime}")

    required_common_web = [
        "link_audit_fast.py",
        "if use_read_only_fastpath:",
    ]
    missing_common_web = [marker for marker in required_common_web if marker not in web_src]
    if missing_common_web:
        raise SystemExit(f"read-only fastpath missing common web markers: {missing_common_web}")

    legacy_web_markers = [
        "is_read_only_prompt",
        "use_read_only_fastpath = audit_only or is_read_only_prompt(raw_prompt)",
        "use_micro_patch = (not use_read_only_fastpath) and is_micro_patch_prompt(raw_prompt)",
    ]

    route_intelligence_web_markers = [
        "from link_route_intelligence import decide_route",
        "route_decision = decide_route",
        "route_decision.get(\"route\") == \"audit_fastpath\"",
        "route_decision.get(\"route\") == \"micro_patch\"",
    ]

    has_legacy_route = all(marker in web_src for marker in legacy_web_markers)
    has_intelligent_route = all(marker in web_src for marker in route_intelligence_web_markers)

    if not (has_legacy_route or has_intelligent_route):
        raise SystemExit("read-only fastpath missing legacy or route-intelligence web markers")

    print("read-only fastpath OK")


def check_specialist_fanout() -> None:
    import json
    import subprocess
    import sys
    import uuid

    script = ROOT / "link_specialist_fanout.py"
    if not script.exists():
        raise SystemExit("specialist fanout missing link_specialist_fanout.py")

    run_id = "healthcheck-fanout-" + uuid.uuid4().hex[:8]
    proc = subprocess.run(
        [sys.executable, str(script), "--run-id", run_id],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    if proc.returncode != 0:
        raise SystemExit(
            "specialist fanout failed: "
            + (proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
        )

    json_path = ROOT / ".agents" / "tool_results" / run_id / "specialist_fanout.json"
    if not json_path.exists():
        raise SystemExit(f"specialist fanout JSON missing: {json_path}")

    data = json.loads(json_path.read_text())
    required = ["repo_state", "route_map", "latest_failures", "safety_status"]
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"specialist fanout JSON missing keys: {missing}")

    if not isinstance(data.get("route_map"), list):
        raise SystemExit("specialist fanout route_map must be a list")

    summary = data.get("summary_path")
    if not summary or not Path(summary).exists():
        raise SystemExit("specialist fanout summary missing")

    print("specialist fanout OK")


def check_route_intelligence() -> None:
    route_src = (ROOT / "link_route_intelligence.py").read_text()
    web_src = (ROOT / "link_web.py").read_text()

    required_route = [
        "def decide_route",
        "def run_specialist_fanout_for_route",
        "audit_fastpath",
        "micro_patch",
        "autonomous",
        "ROUTE_RUNNERS",
    ]
    missing_route = [marker for marker in required_route if marker not in route_src]
    if missing_route:
        raise SystemExit(f"route intelligence missing route markers: {missing_route}")

    required_web = [
        "from link_route_intelligence import decide_route",
        "route_decision = decide_route(raw_prompt, audit_only=audit_only, run_fanout=True)",
        "use_read_only_fastpath = route_decision.get(\"route\") == \"audit_fastpath\"",
        "use_micro_patch = route_decision.get(\"route\") == \"micro_patch\"",
    ]
    missing_web = [marker for marker in required_web if marker not in web_src]
    if missing_web:
        raise SystemExit(f"route intelligence missing web markers: {missing_web}")

    print("route intelligence OK")


def check_progress_planner() -> None:
    src = (ROOT / "link_progress_planner.py").read_text()
    required = [
        "def choose_next_action",
        "broad_prompt_refuses_autonomous",
        "decide_route",
        "latest_engine_reports",
        "latest_fanout_reports",
    ]
    missing = [marker for marker in required if marker not in src]
    if missing:
        raise SystemExit(f"progress planner missing markers: {missing}")

    out = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "link_progress_planner.py"),
            "--prompt",
            "Let's continue on the updates",
            "--json",
        ],
        cwd=ROOT,
        text=True,
    )
    data = json.loads(out)
    if data.get("route", {}).get("route") != "audit_fastpath":
        raise SystemExit("progress planner failed broad prompt audit route")
    if not data.get("broad_prompt_refuses_autonomous"):
        raise SystemExit("progress planner failed broad prompt autonomous refusal")
    print("progress planner OK")


def check_admin_planner() -> None:
    src = (ROOT / "link_admin_planner.py").read_text()
    for needle in [
        "Link Admin Planner",
        "execution_allowed",
        "delegate_to",
        "deepseek",
        "local_qwen",
        "command_guard",
        "file_safety",
        "git_safety",
        "backup_bundle",
    ]:
        if needle not in src:
            raise AssertionError(f"link_admin_planner.py missing {needle!r}")

    out = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "link_admin_planner.py"),
            "--prompt",
            "Let's continue on the updates",
            "--json",
        ],
        text=True,
        cwd=ROOT,
    )
    data = json.loads(out)
    if data.get("execution_allowed") is not False:
        raise AssertionError("admin planner must never allow direct execution")
    if data.get("human_confirmation_required") is not True:
        raise AssertionError("admin planner must require human confirmation")
    if data.get("classification", {}).get("route") != "audit_fastpath":
        raise AssertionError("broad admin prompt must route to audit_fastpath")
    if "link_healthcheck.py" not in " ".join(data.get("required_verification", [])):
        raise AssertionError("admin planner verification must include link_healthcheck.py")
    print("admin planner OK")




def check_delegate_runner() -> None:
    runner = ROOT / "link_delegate_runner.py"
    if not runner.exists():
        raise AssertionError("link_delegate_runner.py missing")

    src = runner.read_text()
    for needle in [
        "Link Delegate Runner",
        "local_qwen",
        "deepseek",
        "DEEPSEEK_API_KEY",
        "LINK_LOCAL_QWEN_MODEL",
        "LINK_LOCAL_QWEN_CMD",
        "LINK_DEEPSEEK_CMD",
        "no_write",
        "model_suggested_commands_not_executed",
    ]:
        if needle not in src:
            raise AssertionError(f"link_delegate_runner.py missing {needle!r}")

    web_dispatch_src = (ROOT / "link_web_admin_dispatch.py").read_text()
    for needle in [
        "link_delegate_runner.py",
        "LINK_ENABLE_MODEL_DELEGATES",
        "_delegate_cmd",
    ]:
        if needle not in web_dispatch_src:
            raise AssertionError(f"link_web_admin_dispatch.py missing delegate hook {needle!r}")

    admin_src = (ROOT / "link_admin_planner.py").read_text()
    if "link_delegate_runner.py" not in admin_src and "delegate_runner" not in admin_src:
        raise AssertionError("link_admin_planner.py missing delegate runner marker")

    out = subprocess.check_output(
        [
            sys.executable,
            str(runner),
            "--prompt",
            "Audit only: delegate runner healthcheck",
            "--providers",
            "none",
            "--dry-run",
            "--json",
            "--no-report",
        ],
        text=True,
        cwd=ROOT,
    )
    data = json.loads(out)
    if data.get("schema_version") != "link_delegate_report_v1":
        raise AssertionError("delegate runner returned wrong schema")
    if data.get("safety", {}).get("no_write") is not True:
        raise AssertionError("delegate runner must be no-write")
    print("delegate runner OK")

def check_web_admin_dispatch() -> None:
    web_src = (ROOT / "link_web.py").read_text()
    dispatch_src = (ROOT / "link_web_admin_dispatch.py").read_text()

    for needle in [
        "link_web_admin_dispatch.py",
        "link_micro_patch.py",
    ]:
        if needle not in web_src:
            raise AssertionError(f"link_web.py missing {needle!r}")

    for needle in [
        "Web admin dispatcher",
        "link_admin_planner.py",
        "link_micro_patch.py",
        "link_audit_fast.py",
        "--plan-only",
        "audit_fastpath",
        "micro_patch",
    ]:
        if needle not in dispatch_src:
            raise AssertionError(f"link_web_admin_dispatch.py missing {needle!r}")

    tmp_prompt = Path("/tmp/link-web-admin-dispatch-healthcheck-prompt.txt")
    tmp_prompt.write_text("Let's continue on the updates", encoding="utf-8")
    out = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "link_web_admin_dispatch.py"),
            "--prompt-file",
            str(tmp_prompt),
            "--json",
            "--plan-only",
        ],
        text=True,
        cwd=ROOT,
    )
    try:
        tmp_prompt.unlink()
    except OSError:
        pass
    data = json.loads(out)
    route = data.get("classification", {}).get("route")
    if route != "audit_fastpath":
        raise AssertionError(f"broad web admin prompt should route audit_fastpath, got {route!r}")
    if data.get("human_confirmation_required") is not True:
        raise AssertionError("web admin dispatch planner must require human confirmation")

    safe_text_micro = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "link_web_admin_dispatch.py"),
            "--prompt",
            "MICRO PATCH: target file: README.md content: `Link web admin dispatch smoke`",
            "--json",
            "--plan-only",
        ],
        text=True,
        cwd=ROOT,
    )
    micro_data = json.loads(safe_text_micro)
    micro_class = micro_data.get("classification", {})
    repo_dirty = bool(micro_data.get("repo", {}).get("dirty"))

    if repo_dirty:
        if micro_class.get("route") != "audit_fastpath":
            raise AssertionError("dirty repo safe text micro prompt should be guarded to audit_fastpath")
        if micro_class.get("reason") != "repo_dirty_never_execute_or_delegate_patch":
            raise AssertionError("dirty repo safe text micro prompt should explain dirty guard")
    else:
        if micro_class.get("route") != "micro_patch":
            raise AssertionError("clean repo safe text micro prompt should route to micro_patch")
        if micro_class.get("risk") == "high":
            raise AssertionError("safe text micro prompt should not become high risk from content words")

    print("web admin dispatch OK")






def check_qa_repair_routing_contract() -> None:
    from qa_repair_routing_contract import (
        route_qa_result,
        validate_qa_repair_route,
    )

    repair = route_qa_result(
        "REVISE",
        "BLOCKING-1: Missing healthcheck update. Must fix before approval.",
        ["link_healthcheck.py"],
    )
    repair_problems = validate_qa_repair_route(repair)

    if repair["route"] != "repair_required":
        raise SystemExit("qa repair routing failed to route blocking QA to repair")
    if repair["allowed_to_commit"]:
        raise SystemExit("qa repair routing allowed commit despite blocking QA")
    if repair_problems:
        raise SystemExit("qa repair routing repair-case failures:\n" + "\n".join(repair_problems))

    approval = route_qa_result(
        "APPROVE",
        "QA PASS. Ready for senior review.",
        ["link_healthcheck.py"],
    )
    approval_problems = validate_qa_repair_route(approval)

    if approval["route"] != "approval_ready":
        raise SystemExit("qa repair routing failed to route approval to approval_ready")
    if not approval["allowed_to_commit"]:
        raise SystemExit("qa repair routing did not allow clean approval")
    if approval_problems:
        raise SystemExit("qa repair routing approval-case failures:\n" + "\n".join(approval_problems))

    print("qa repair routing contract OK")

def check_upgrade_diff_receipt_crosscheck() -> None:
    from upgrade_diff_receipt_crosscheck import (
        crosscheck_diff_receipt,
        synthetic_lu08_receipt,
    )

    required = [
        "upgrade_diff_receipt_crosscheck.py",
        "link_healthcheck.py",
        "link_upgrade_registry.py",
        "UPGRADES.md",
    ]

    problems = crosscheck_diff_receipt(
        synthetic_lu08_receipt(),
        required_files=required,
        required_subject_contains="LU08",
        required_upgrade_id="LU08",
    )
    if problems:
        raise SystemExit("upgrade diff receipt cross-check failures:\n" + "\n".join(problems))

    bad = dict(synthetic_lu08_receipt())
    bad["changed_files"] = ["link_healthcheck.py"]
    bad_problems = crosscheck_diff_receipt(
        bad,
        required_files=required,
        required_subject_contains="LU08",
        required_upgrade_id="LU08",
    )
    if not any(item.startswith("changed_file_missing::upgrade_diff_receipt_crosscheck.py") for item in bad_problems):
        raise SystemExit("upgrade diff receipt cross-check negative test did not catch missing file")

    print("upgrade diff receipt cross-check OK")

def check_upgrade_status_badges() -> None:
    from pathlib import Path
    from link_upgrade_status import render_upgrade_badges, upgrade_status_rows

    rows = upgrade_status_rows()
    ids = {row["id"] for row in rows}
    required = {"LU01", "LU02", "LU03", "LU04", "LU05", "LU06", "LU07", "LU08", "LU09", "LU10", "LU11", "LU12", "LU13", "LU14"}
    missing = sorted(required - ids)
    if missing:
        raise SystemExit("upgrade status badges missing ids: " + ", ".join(missing))

    html = render_upgrade_badges()
    required_html = [
        "upgrade-status-panel",
        "upgrade-badge-implemented",
        "LU07",
        "Implementation status dashboard badges",
    ]
    missing_html = [needle for needle in required_html if needle not in html]
    if missing_html:
        raise SystemExit("upgrade status badge html missing: " + ", ".join(missing_html))

    dashboard_src = Path("link_factory_dashboard.py").read_text()
    dashboard_needles = [
        "from link_upgrade_status import render_upgrade_badges",
        "/upgrade-status",
        "render_upgrade_badges()",
    ]
    missing_dashboard = [needle for needle in dashboard_needles if needle not in dashboard_src]
    if missing_dashboard:
        raise SystemExit("dashboard upgrade status wiring missing: " + ", ".join(missing_dashboard))

    print("upgrade status badges OK")

def check_planner_acceptance_contract() -> None:
    import tempfile
    from pathlib import Path

    from planner_acceptance_contract import (
        build_acceptance_contract,
        evaluate_acceptance_contract,
        validate_acceptance_contract,
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "implemented.txt").write_text("done", encoding="utf-8")

        contract = build_acceptance_contract(
            upgrade_id="LUXX",
            title="Example accepted upgrade",
            required_files=["implemented.txt"],
            required_healthcheck_markers=["example marker OK"],
            required_commit_subject="feat: example accepted upgrade",
            registry_id="LUXX",
        )

        clean = validate_acceptance_contract(
            contract,
            repo_root=root,
            healthcheck_output="example marker OK\nLINK HEALTHCHECK PASSED",
            git_log_output="abc123 feat: example accepted upgrade",
            registry_ids={"LUXX"},
        )
        if clean:
            raise SystemExit("planner acceptance contract clean case failed:\n" + "\n".join(clean))

        checks = [
            (
                {**contract, "required_files": ["missing.txt"]},
                "example marker OK",
                "abc123 feat: example accepted upgrade",
                {"LUXX"},
                "missing required file",
            ),
            (
                contract,
                "LINK HEALTHCHECK PASSED",
                "abc123 feat: example accepted upgrade",
                {"LUXX"},
                "missing healthcheck marker",
            ),
            (
                contract,
                "example marker OK",
                "abc123 other commit",
                {"LUXX"},
                "missing expected commit subject",
            ),
            (
                contract,
                "example marker OK",
                "abc123 feat: example accepted upgrade",
                set(),
                "missing registry id",
            ),
        ]

        for test_contract, health, log, registry_ids, expected in checks:
            problems = validate_acceptance_contract(
                test_contract,
                repo_root=root,
                healthcheck_output=health,
                git_log_output=log,
                registry_ids=registry_ids,
            )
            if not any(expected in p for p in problems):
                raise SystemExit("planner acceptance contract failed to catch: " + expected)

        result = evaluate_acceptance_contract(
            contract,
            repo_root=root,
            healthcheck_output="example marker OK",
            git_log_output="abc123 feat: example accepted upgrade",
            registry_ids={"LUXX"},
        )
        if not result.get("accepted"):
            raise SystemExit("planner acceptance contract evaluate() did not accept clean contract")

    print("planner acceptance contract OK")

def check_upgrade_registry() -> None:
    import link_upgrade_registry

    problems = link_upgrade_registry.validate_registry()
    if problems:
        raise SystemExit("upgrade registry failures:\n" + "\n".join(problems))

    required = {"LU01", "LU02", "LU03", "LU04", "LU05", "LU06", "LU07", "LU08", "LU09", "LU10", "LU11", "LU12", "LU13", "LU14", "LU15", "LU16", "LU17", "LU18", "LU19", "LU20"}
    implemented = set(link_upgrade_registry.implemented_upgrade_ids())
    missing = sorted(required - implemented)
    if missing:
        raise SystemExit("upgrade registry missing implemented upgrades: " + ", ".join(missing))

    print("upgrade registry OK")



def check_upgrade_evidence_bundle() -> None:
    import tempfile

    from upgrade_evidence_bundle import export_upgrade_evidence_bundle, validate_evidence_bundle

    with tempfile.TemporaryDirectory() as tmp:
        bundle = export_upgrade_evidence_bundle("LU09", tmp)
        problems = validate_evidence_bundle(bundle)
        if problems:
            raise SystemExit("upgrade evidence bundle failures:\n" + "\n".join(problems))

    print("upgrade evidence bundle OK")



def check_healthcheck_evidence_archive() -> None:
    import tempfile

    from healthcheck_evidence_archive import (
        archive_healthcheck_output,
        validate_healthcheck_archive,
    )

    with tempfile.TemporaryDirectory() as tmp:
        latest = None
        for i in range(4):
            latest = archive_healthcheck_output(
                output=f"fake healthcheck output {i}\nLINK HEALTHCHECK PASSED\n",
                exit_code=0,
                archive_root=tmp,
                retain=2,
                label="healthcheck_test",
            )

        if latest is None:
            raise SystemExit("healthcheck evidence archive did not create archive")

        problems = validate_healthcheck_archive(latest)
        if problems:
            raise SystemExit("healthcheck evidence archive failures:\n" + "\n".join(problems))

        remaining = [p for p in __import__("pathlib").Path(tmp).iterdir() if p.is_dir()]
        if len(remaining) != 2:
            raise SystemExit(f"healthcheck evidence archive retention failed: {len(remaining)} archives remain")

    print("healthcheck evidence archive OK")



def check_healthcheck_evidence_index() -> None:
    from healthcheck_evidence_index import self_test

    problems = self_test()
    if problems:
        raise SystemExit("healthcheck evidence index failures:\n" + "\n".join(problems))

    print("healthcheck evidence index OK")



def check_evidence_rollback_advisor() -> None:
    from evidence_rollback_advisor import self_test

    problems = self_test()
    if problems:
        raise SystemExit("evidence rollback advisor failures:\n" + "\n".join(problems))

    print("evidence rollback advisor OK")



def check_rollback_advisor_dashboard() -> None:
    from rollback_advisor_dashboard import self_test

    problems = self_test()
    if problems:
        raise SystemExit("rollback advisor dashboard failures:\n" + "\n".join(problems))

    print("rollback advisor dashboard OK")



def check_rollback_advisor_cli() -> None:
    from link_rollback_advisor import self_test

    problems = self_test()
    if problems:
        raise SystemExit("rollback advisor CLI failures:\n" + "\n".join(problems))

    print("rollback advisor CLI OK")



def check_rollback_advisor_web_admin_route() -> None:
    from pathlib import Path

    from rollback_advisor_web_admin_route import rollback_advisor_web_admin_command, self_test

    problems = self_test()
    if problems:
        raise SystemExit("rollback advisor web admin route failures:\n" + "\n".join(problems))

    dispatch = Path("link_web_admin_dispatch.py").read_text()
    required = [
        "from rollback_advisor_web_admin_route import rollback_advisor_web_admin_plan",
        "rollback_advisor_web_admin_plan(prompt)",
    ]
    missing = [needle for needle in required if needle not in dispatch]
    if missing:
        raise SystemExit("rollback advisor web admin dispatch wiring missing: " + ", ".join(missing))

    dashboard = rollback_advisor_web_admin_command("rollback advisor dashboard json")
    if dashboard != ["python3", "link_rollback_advisor.py", "dashboard", "--json"]:
        raise SystemExit("rollback advisor web admin dashboard route failed")

    print("rollback advisor web admin route OK")



def check_rollback_recovery_plan_exporter() -> None:
    import tempfile

    from rollback_recovery_plan import (
        export_rollback_recovery_plan,
        self_test,
        validate_recovery_plan,
    )

    problems = self_test()
    if problems:
        raise SystemExit("rollback recovery plan exporter failures:\n" + "\n".join(problems))

    sample = {
        "recommendation": "ADVISE_ROLLBACK_TO_LAST_PASS",
        "reason": "healthcheck sample failure",
        "current_head": "HEADSHA",
        "rollback_candidate": "GOODSHA",
        "latest_archive": "sample_archive",
        "latest_status": "failed",
    }

    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = export_rollback_recovery_plan(tmp, sample)
        json_path = plan_dir / "rollback_recovery_plan.json"
        md_path = plan_dir / "rollback_recovery_plan.md"
        if not json_path.exists():
            raise SystemExit("rollback recovery plan JSON missing")
        if not md_path.exists():
            raise SystemExit("rollback recovery plan markdown missing")
        text = md_path.read_text()
        if "# REVIEW ONLY: git reset --hard GOODSHA" not in text:
            raise SystemExit("rollback recovery plan hard reset is not guarded")

    print("rollback recovery plan exporter OK")



def check_rollback_recovery_plan_web_admin_route() -> None:
    from rollback_recovery_plan_web_admin_route import (
        build_route_result,
        rollback_recovery_plan_web_admin_command,
        self_test,
    )

    problems = self_test()
    if problems:
        raise SystemExit("rollback recovery plan web admin route failures:\n" + "\n".join(problems))

    command = rollback_recovery_plan_web_admin_command("export rollback recovery plan as json")
    expected = ["python3", "rollback_recovery_plan.py", "--json"]
    if command != expected:
        raise SystemExit(f"rollback recovery plan web route command mismatch: {command!r}")

    result = build_route_result("guarded recovery plan")
    if not result.get("guarded"):
        raise SystemExit("rollback recovery plan web route is not guarded")
    if result.get("destructive"):
        raise SystemExit("rollback recovery plan web route should not be destructive")

    print("rollback recovery plan web admin route OK")



def check_recovery_plan_dashboard_card() -> None:
    from recovery_plan_dashboard_card import (
        recovery_plan_dashboard_payload,
        render_recovery_plan_dashboard_card,
        sample_plan,
        self_test,
    )

    problems = self_test()
    if problems:
        raise SystemExit("recovery plan dashboard card failures:\n" + "\n".join(problems))

    plan = sample_plan()
    payload = recovery_plan_dashboard_payload(plan)
    html = render_recovery_plan_dashboard_card(plan)

    if payload.get("destructive"):
        raise SystemExit("recovery plan dashboard payload should be non-destructive")
    if 'data-link-card="recovery-plan"' not in html:
        raise SystemExit("recovery plan dashboard card marker missing")
    if "<form" in html.lower():
        raise SystemExit("recovery plan dashboard card must not expose a destructive form")

    print("recovery plan dashboard card OK")



def check_recovery_plan_dashboard_web_admin_integration() -> None:
    from recovery_plan_dashboard_web_admin import (
        build_recovery_plan_dashboard_web_response,
        recovery_plan_dashboard_web_admin_command,
        render_recovery_plan_dashboard_web_response,
        self_test as dashboard_web_self_test,
    )

    problems = dashboard_web_self_test()
    if problems:
        raise SystemExit(
            "recovery plan dashboard web admin integration failures:\n"
            + "\n".join(problems)
        )

    command = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard")
    if not command:
        raise SystemExit("recovery plan dashboard web admin command routing failed")

    json_command = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard json")
    if not json_command:
        raise SystemExit("recovery plan dashboard web admin json command routing failed")

    response = build_recovery_plan_dashboard_web_response()
    html = render_recovery_plan_dashboard_web_response()

    if response.get("destructive") or response.get("dangerous"):
        raise SystemExit("recovery plan dashboard web admin response must be non-destructive")

    if "recovery-plan" not in html:
        raise SystemExit("recovery plan dashboard web admin card marker missing")

    print("recovery plan dashboard web admin integration OK")

def check_latest_recovery_plan_loader() -> None:
    from latest_recovery_plan_loader import validate_latest_recovery_plan_loader

    problems = validate_latest_recovery_plan_loader()
    if problems:
        raise SystemExit("latest recovery plan loader failures:\n" + "\n".join(problems))

    print("latest recovery plan loader OK")



def check_lu22_upgrade_finalizer_and_safe_apply_workflow() -> None:
    import subprocess
    subprocess.check_call(["python3", "link_upgrade_finalizer.py", "--self-test"])
    print("upgrade finalizer OK")


def check_latest_recovery_plan_dashboard_execution_receipts() -> None:
    from latest_recovery_plan_dashboard_receipts import validate_latest_recovery_dashboard_receipts

    problems = validate_latest_recovery_dashboard_receipts()
    if problems:
        raise SystemExit("latest recovery plan dashboard execution receipts failures:\\n" + "\\n".join(problems))

    print("latest recovery plan dashboard execution receipts OK")

def check_latest_recovery_plan_dashboard_receipt_web_admin_route() -> None:
    from latest_recovery_plan_dashboard_receipt_web_admin import (
        build_latest_recovery_plan_dashboard_receipt_web_response,
        latest_recovery_plan_dashboard_receipt_web_admin_command,
        render_latest_recovery_plan_dashboard_receipt_web_response,
        self_test as latest_receipt_web_admin_self_test,
    )

    problems = latest_receipt_web_admin_self_test()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt web admin route failures:\n"
            + "\n".join(problems)
        )

    command = latest_recovery_plan_dashboard_receipt_web_admin_command(
        "show latest recovery plan dashboard receipt"
    )
    if not command:
        raise SystemExit("latest recovery plan dashboard receipt web admin command routing failed")

    response = build_latest_recovery_plan_dashboard_receipt_web_response(write=False)
    if response.get("non_destructive") is not True:
        raise SystemExit("latest recovery plan dashboard receipt web admin response must be non-destructive")

    rendered = render_latest_recovery_plan_dashboard_receipt_web_response(response)
    if "latest-recovery-dashboard-receipt" not in rendered:
        raise SystemExit("latest recovery plan dashboard receipt web admin marker missing")

    forbidden = ("<form", "method=\"post\"", "rm -rf", "git reset --hard", "git clean -fdx")
    lowered = rendered.lower()
    for item in forbidden:
        if item in lowered:
            raise SystemExit(f"latest recovery plan dashboard receipt web admin contains forbidden text: {item}")

    print("latest recovery plan dashboard receipt web admin route OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index import (
        validate_latest_recovery_plan_dashboard_receipt_evidence_index,
    )

    problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_route() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_web_admin import self_test

    problems = self_test()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index web admin route failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index web admin route OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration import (
        self_test,
    )

    problems = self_test()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index web admin integration OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_receipts import (
        validate_latest_recovery_receipt_evidence_index_execution_receipt,
    )

    problems = validate_latest_recovery_receipt_evidence_index_execution_receipt()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin_route() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin import (
        validate_execution_receipt_web_admin_route,
    )

    problems = validate_execution_receipt_web_admin_route()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt web admin route failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt web admin route OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin_integration() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin_integration import (
        validate_latest_recovery_receipt_evidence_index_execution_receipt_web_admin_integration,
    )

    problems = validate_latest_recovery_receipt_evidence_index_execution_receipt_web_admin_integration()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt web admin integration OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index import (
        validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index,
    )

    problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt evidence index failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt evidence index OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin import (
        validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route,
    )

    problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin route failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin route OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration import (
        validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration,
    )

    problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin integration OK")

def check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt() -> None:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_receipts import (
        validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt,
    )

    problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt()
    if problems:
        raise SystemExit(
            "latest recovery plan dashboard receipt evidence index execution receipt evidence index execution receipt failures:\n"
            + "\n".join(problems)
        )
    from link_research_archive_candidate_shortlist_web_admin_route import (
        MARKER as research_candidate_shortlist_web_admin_route_marker,
        validate_research_candidate_shortlist_web_admin_route,
    )

    research_candidate_shortlist_web_admin_route_failures = validate_research_candidate_shortlist_web_admin_route()
    if research_candidate_shortlist_web_admin_route_failures:
        raise AssertionError(
            "research archive candidate shortlist web admin route failed: "
            + "; ".join(research_candidate_shortlist_web_admin_route_failures)
        )
    print(research_candidate_shortlist_web_admin_route_marker)

    print("latest recovery plan dashboard receipt evidence index execution receipt evidence index execution receipt OK")

def check_link_workflow_spec_layer() -> None:
    from link_workflow_spec import validate_link_workflow_spec_layer

    problems = validate_link_workflow_spec_layer()
    if problems:
        raise SystemExit(
            "workflow spec layer failures:\n"
            + "\n".join(problems)
        )
    print("workflow spec layer OK")

def check_link_workflow_preflight_executor() -> None:
    from link_workflow_preflight_executor import validate_link_workflow_preflight_executor

    problems = validate_link_workflow_preflight_executor()
    if problems:
        raise SystemExit(
            "workflow spec preflight executor failures:\n"
            + "\n".join(problems)
        )
    print("workflow spec preflight executor OK")

def check_link_workflow_preflight_receipt_index() -> None:
    from link_workflow_preflight_receipt_index import validate_workflow_preflight_receipt_index

    problems = validate_workflow_preflight_receipt_index()
    if problems:
        raise SystemExit(
            "workflow preflight receipt index failures:\n"
            + "\n".join(problems)
        )
    print("workflow preflight receipt index OK")

def check_link_workflow_preflight_receipt_index_web_admin_route() -> None:
    from link_workflow_preflight_receipt_index_web_admin import (
        validate_workflow_preflight_receipt_index_web_admin_route,
    )

    problems = validate_workflow_preflight_receipt_index_web_admin_route()
    if problems:
        raise SystemExit(
            "workflow preflight receipt index web admin route failures:\n"
            + "\n".join(problems)
        )
    print("workflow preflight receipt index web admin route OK")

def check_link_workflow_preflight_receipt_index_web_admin_integration() -> None:
    from link_workflow_preflight_receipt_index_web_admin_integration import (
        validate_workflow_preflight_receipt_index_web_admin_integration,
    )

    problems = validate_workflow_preflight_receipt_index_web_admin_integration()
    if problems:
        raise SystemExit(
            "workflow preflight receipt index web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("workflow preflight receipt index web admin integration OK")

def check_link_workflow_step_executor() -> None:
    from link_workflow_step_executor import validate_workflow_step_executor

    problems = validate_workflow_step_executor()
    if problems:
        raise SystemExit(
            "workflow step executor failures:\n"
            + "\n".join(problems)
        )
    print("workflow step executor OK")

def check_link_workflow_step_receipt_index() -> None:
    from link_workflow_step_receipt_index import validate_workflow_step_receipt_index

    problems = validate_workflow_step_receipt_index()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index OK")

def check_link_workflow_step_receipt_index_web_admin_route() -> None:
    from link_workflow_step_receipt_index_web_admin import (
        validate_workflow_step_receipt_index_web_admin_route,
    )

    problems = validate_workflow_step_receipt_index_web_admin_route()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index web admin route failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index web admin route OK")

def check_link_workflow_step_receipt_index_web_admin_integration() -> None:
    from link_workflow_step_receipt_index_web_admin_integration import (
        validate_workflow_step_receipt_index_web_admin_integration,
    )

    problems = validate_workflow_step_receipt_index_web_admin_integration()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index web admin integration OK")

def check_link_workflow_step_receipt_index_execution_receipt() -> None:
    from link_workflow_step_receipt_index_receipts import (
        validate_workflow_step_receipt_index_execution_receipt,
    )

    problems = validate_workflow_step_receipt_index_execution_receipt()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index execution receipt failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index execution receipt OK")

def check_link_workflow_step_receipt_index_execution_receipt_web_admin_route() -> None:
    from link_workflow_step_receipt_index_receipts_web_admin import (
        validate_workflow_step_receipt_index_execution_receipt_web_admin_route,
    )

    problems = validate_workflow_step_receipt_index_execution_receipt_web_admin_route()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index execution receipt web admin route failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index execution receipt web admin route OK")

def check_link_workflow_step_receipt_index_execution_receipt_web_admin_integration() -> None:
    from link_workflow_step_receipt_index_receipts_web_admin_integration import (
        validate_workflow_step_receipt_index_execution_receipt_web_admin_integration,
    )

    problems = validate_workflow_step_receipt_index_execution_receipt_web_admin_integration()
    if problems:
        raise SystemExit(
            "workflow step execution receipt index execution receipt web admin integration failures:\n"
            + "\n".join(problems)
        )
    print("workflow step execution receipt index execution receipt web admin integration OK")

def check_research_archive_intake_miner() -> None:
    from link_research_archive_miner import validate_research_archive_miner

    problems = validate_research_archive_miner()
    if problems:
        raise SystemExit(
            "research archive intake miner failures:\n"
            + "\n".join(problems)
        )
    print("research archive intake miner OK")

    from link_research_archive_intake_web_admin import (
        validate_research_archive_intake_web_admin_route,
    )

    research_archive_intake_web_admin_problems = (
        validate_research_archive_intake_web_admin_route()
    )
    if research_archive_intake_web_admin_problems:
        raise SystemExit(
            "research archive intake miner web admin route failures:\n- "
            + "\n- ".join(research_archive_intake_web_admin_problems)
        )

    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    routed_research_archive_intake = recovery_plan_dashboard_web_admin_command(
        "show research archive intake json"
    )
    if not routed_research_archive_intake:
        raise SystemExit("research archive intake miner web admin route did not dispatch")
    joined_research_archive_intake_route = "\n".join(routed_research_archive_intake)
    if "research_archive_intake_web_admin" not in joined_research_archive_intake_route:
        raise SystemExit("research archive intake miner web admin route payload missing kind")
    if "research archive intake" not in joined_research_archive_intake_route.lower():
        raise SystemExit("research archive intake miner web admin route payload missing title")

    print("research archive intake miner web admin route OK")

    from link_research_archive_intake_web_admin_integration import (
        validate_research_archive_intake_web_admin_integration,
    )

    research_archive_intake_web_admin_integration_problems = (
        validate_research_archive_intake_web_admin_integration()
    )
    if research_archive_intake_web_admin_integration_problems:
        raise SystemExit(
            "research archive intake miner web admin integration failures:\n- "
            + "\n- ".join(research_archive_intake_web_admin_integration_problems)
        )
    print("research archive intake miner web admin integration OK")

    from link_research_archive_candidate_detail_viewer import (
        validate_research_archive_candidate_detail_viewer,
    )

    research_archive_candidate_detail_problems = (
        validate_research_archive_candidate_detail_viewer()
    )
    if research_archive_candidate_detail_problems:
        raise SystemExit(
            "research archive intake candidate detail viewer failures:\n- "
            + "\n- ".join(research_archive_candidate_detail_problems)
        )

    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    routed_research_candidate_detail = recovery_plan_dashboard_web_admin_command(
        "show research archive candidate detail json top 1"
    )
    if not routed_research_candidate_detail:
        raise SystemExit("research archive candidate detail viewer did not dispatch")
    joined_research_candidate_detail = "\n".join(routed_research_candidate_detail)
    if "research_archive_candidate_detail_viewer" not in joined_research_candidate_detail:
        raise SystemExit("research archive candidate detail viewer payload missing kind")
    if "research archive candidate detail" not in joined_research_candidate_detail.lower():
        raise SystemExit("research archive candidate detail viewer payload missing title")

    print("research archive intake candidate detail viewer OK")

    from link_research_archive_candidate_detail_web_admin_integration import (
        validate_research_archive_candidate_detail_web_admin_integration,
    )

    research_archive_candidate_detail_integration_problems = (
        validate_research_archive_candidate_detail_web_admin_integration()
    )
    if research_archive_candidate_detail_integration_problems:
        raise SystemExit(
            "research archive candidate detail web admin integration failures:\n- "
            + "\n- ".join(research_archive_candidate_detail_integration_problems)
        )

    print("research archive candidate detail web admin integration OK")

    from link_research_archive_candidate_shortlist_exporter import (
        validate_research_candidate_shortlist_exporter,
    )

    research_candidate_shortlist_problems = validate_research_candidate_shortlist_exporter()
    if research_candidate_shortlist_problems:
        raise SystemExit(
            "research archive candidate shortlist exporter failures:\n- "
            + "\n- ".join(research_candidate_shortlist_problems)
        )

    print("research archive candidate shortlist exporter OK")



def check_research_archive_candidate_shortlist_web_admin_integration() -> None:
    from link_research_archive_candidate_shortlist_web_admin_integration import (
        validate_research_candidate_shortlist_web_admin_integration,
    )

    failures = validate_research_candidate_shortlist_web_admin_integration()
    if failures:
        print("research archive candidate shortlist web admin integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist web admin integration OK")



def check_research_archive_candidate_shortlist_dashboard_integration() -> None:
    from link_research_archive_candidate_shortlist_dashboard_integration import (
        validate_research_candidate_shortlist_dashboard_integration,
    )

    failures = validate_research_candidate_shortlist_dashboard_integration()
    if failures:
        print("research archive candidate shortlist dashboard integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist dashboard integration OK")


def check_research_archive_candidate_shortlist_dashboard_web_admin_route() -> None:
    from link_research_archive_candidate_shortlist_dashboard_web_admin_route import (
        validate_research_candidate_shortlist_dashboard_web_admin_route,
    )

    failures = validate_research_candidate_shortlist_dashboard_web_admin_route()
    if failures:
        print("research archive candidate shortlist dashboard web admin route FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist dashboard web admin route OK")


def check_research_archive_candidate_shortlist_dashboard_web_admin_integration() -> None:
    from link_research_archive_candidate_shortlist_dashboard_web_admin_integration import (
        validate_research_candidate_shortlist_dashboard_web_admin_integration,
    )

    failures = validate_research_candidate_shortlist_dashboard_web_admin_integration()
    if failures:
        print("research archive candidate shortlist dashboard web admin integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist dashboard web admin integration OK")


def check_research_archive_candidate_shortlist_dashboard_web_admin_dispatch() -> None:
    from link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch import (
        validate_research_candidate_shortlist_dashboard_web_admin_dispatch,
    )

    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist dashboard web admin dispatch OK")


def check_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration() -> None:
    from link_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration import (
        validate_research_candidate_shortlist_dashboard_web_admin_dispatch_integration,
    )

    failures = validate_research_candidate_shortlist_dashboard_web_admin_dispatch_integration()
    if failures:
        print("research archive candidate shortlist dashboard web admin dispatch integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("research archive candidate shortlist dashboard web admin dispatch integration OK")

def main() -> None:
    if "--self-test60" in sys.argv:
        check_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration()
        return
    if "--self-test59" in sys.argv:
        check_research_archive_candidate_shortlist_dashboard_web_admin_dispatch()
        return
    if "--self-test58" in sys.argv:
        check_research_archive_candidate_shortlist_dashboard_web_admin_integration()
        return
    check_research_archive_candidate_shortlist_dashboard_web_admin_dispatch_integration()
    check_removed_junk_absent()
    check_compile()
    check_imports()
    check_command_guard()
    check_capability_gate()
    check_context_truncation_contract()
    check_context_manifest_integrity_contract()
    check_execution_receipts()
    check_execution_snapshots()
    check_web_admin_snapshot_wiring()
    check_upgrade_registry()
    check_planner_acceptance_contract()
    check_upgrade_status_badges()
    check_upgrade_diff_receipt_crosscheck()
    check_qa_repair_routing_contract()
    check_upgrade_evidence_bundle()
    check_healthcheck_evidence_archive()
    check_healthcheck_evidence_index()
    check_evidence_rollback_advisor()
    check_rollback_advisor_dashboard()
    check_rollback_advisor_cli()
    check_rollback_advisor_web_admin_route()
    check_rollback_recovery_plan_exporter()
    check_rollback_recovery_plan_web_admin_route()
    check_recovery_plan_dashboard_card()
    check_recovery_plan_dashboard_web_admin_integration()
    check_latest_recovery_plan_loader()
    print("recovery plan dashboard latest-plan loader OK")
    check_recovery_plan_dashboard_latest_plan_integration()
    check_lu22_upgrade_finalizer_and_safe_apply_workflow()
    check_latest_recovery_plan_dashboard_execution_receipts()
    check_latest_recovery_plan_dashboard_receipt_web_admin_route()
    check_latest_recovery_plan_dashboard_receipt_evidence_index()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_route()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin_route()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin_integration()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration()
    check_link_workflow_spec_layer()
    check_link_workflow_preflight_executor()
    check_link_workflow_preflight_receipt_index()
    check_link_workflow_preflight_receipt_index_web_admin_route()
    check_link_workflow_preflight_receipt_index_web_admin_integration()
    check_link_workflow_step_executor()
    check_link_workflow_step_receipt_index()
    check_link_workflow_step_receipt_index_web_admin_route()
    check_link_workflow_step_receipt_index_web_admin_integration()
    check_link_workflow_step_receipt_index_execution_receipt()
    check_link_workflow_step_receipt_index_execution_receipt_web_admin_route()
    check_link_workflow_step_receipt_index_execution_receipt_web_admin_integration()
    check_research_archive_intake_miner()
    check_research_archive_candidate_shortlist_web_admin_integration()
    check_research_archive_candidate_shortlist_dashboard_integration()
    check_research_archive_candidate_shortlist_dashboard_web_admin_route()
    check_research_archive_candidate_shortlist_dashboard_web_admin_integration()
    check_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt()
    check_file_safety()
    check_git_safety()
    check_task_tracker()
    check_context_budget()
    check_queue_status()
    check_dead_code_audit()
    check_runtime_legacy_audit()
    check_web_engine_wiring()
    check_engine_expected_change_guard()
    check_runtime_sources_tracked()
    check_upgrade_pack()
    check_policy_upgrade_pack()
    check_specialist_fanout()
    check_readonly_fastpath()
    check_micro_patch_fastpath()
    check_web_status_normalization()
    check_loop_controller()
    check_forbidden_junk()
    check_progress_planner()
    check_admin_planner()
    check_delegate_runner()
    check_web_admin_dispatch()
    print("LINK HEALTHCHECK PASSED")


if __name__ == "__main__":
    main()
