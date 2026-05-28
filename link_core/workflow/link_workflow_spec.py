#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MARKER = "workflow spec layer OK"

WORKFLOW_SPEC_KIND = "link_workflow_spec"
WORKFLOW_SPEC_SCHEMA_VERSION = 1

REQUIRED_TOP_LEVEL_FIELDS = (
    "kind",
    "schema_version",
    "workflow_id",
    "goal",
    "inputs",
    "required_tools",
    "preflight_checks",
    "steps",
    "expected_artifacts",
    "receipt_schema",
    "rollback_policy",
    "verification_commands",
)

ALLOWED_STEP_TYPES = {
    "inspect",
    "plan",
    "edit",
    "test",
    "review",
    "commit",
    "report",
}

SAFE_COMMAND_PREFIXES = (
    "python3 ",
    "python ",
    "pytest",
    "git status",
    "git diff",
    "git log",
    "ls ",
    "pwd",
    "grep ",
    "rg ",
)

DENIED_COMMAND_PATTERNS = (
    "rm -rf /",
    "rm -rf ~",
    "git reset --hard",
    "git clean -fd",
    "git clean -fdx",
    "git push --force",
    "curl ",
    "wget ",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "workflow"


def sample_workflow_spec() -> dict[str, Any]:
    return {
        "kind": WORKFLOW_SPEC_KIND,
        "schema_version": WORKFLOW_SPEC_SCHEMA_VERSION,
        "workflow_id": "lu36-workflow-spec-layer",
        "created_at": utc_now(),
        "goal": "Add a deterministic workflow specification layer for Link orchestration.",
        "inputs": {
            "repo_root": ".",
            "upgrade_id": "LU36",
            "mode": "non_destructive",
        },
        "required_tools": [
            "python3",
            "git",
        ],
        "preflight_checks": [
            {
                "id": "repo-clean",
                "description": "Confirm git working tree is clean before starting.",
                "command": "git status --short",
                "expect_empty_stdout": True,
                "required": True,
            },
            {
                "id": "compile-healthcheck",
                "description": "Confirm healthcheck can compile after changes.",
                "command": "python3 -m py_compile link_healthcheck.py link_upgrade_registry.py",
                "required": True,
            },
        ],
        "steps": [
            {
                "id": "write-module",
                "title": "Write workflow spec module",
                "type": "edit",
                "depends_on": [],
                "parallelizable": False,
                "expected_outputs": [
                    "link_workflow_spec.py",
                ],
            },
            {
                "id": "self-test",
                "title": "Run workflow spec self-test",
                "type": "test",
                "depends_on": [
                    "write-module",
                ],
                "parallelizable": False,
                "expected_outputs": [
                    MARKER,
                ],
            },
            {
                "id": "healthcheck",
                "title": "Run full Link healthcheck",
                "type": "test",
                "depends_on": [
                    "self-test",
                ],
                "parallelizable": False,
                "expected_outputs": [
                    "LINK HEALTHCHECK PASSED",
                ],
            },
        ],
        "expected_artifacts": [
            {
                "path": "link_workflow_spec.py",
                "kind": "module",
                "required": True,
            },
            {
                "path": "link_healthcheck.py",
                "kind": "healthcheck integration",
                "required": True,
            },
            {
                "path": "link_upgrade_registry.py",
                "kind": "upgrade registry integration",
                "required": True,
            },
        ],
        "receipt_schema": {
            "kind": "link_workflow_execution_receipt",
            "required_fields": [
                "workflow_id",
                "ok",
                "started_at",
                "finished_at",
                "steps",
                "problems",
                "non_destructive",
            ],
        },
        "rollback_policy": {
            "non_destructive": True,
            "rollback_candidate": "previous stable-lu tag",
            "forbidden_commands": [
                "git reset --hard",
                "git clean -fdx",
                "rm -rf",
            ],
        },
        "verification_commands": [
            "python3 link_workflow_spec.py --self-test",
            "python3 link_healthcheck.py",
        ],
    }


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(spec)
    normalized.setdefault("kind", WORKFLOW_SPEC_KIND)
    normalized.setdefault("schema_version", WORKFLOW_SPEC_SCHEMA_VERSION)
    normalized.setdefault("created_at", utc_now())
    normalized.setdefault("inputs", {})
    normalized.setdefault("required_tools", [])
    normalized.setdefault("preflight_checks", [])
    normalized.setdefault("steps", [])
    normalized.setdefault("expected_artifacts", [])
    normalized.setdefault("receipt_schema", {})
    normalized.setdefault("rollback_policy", {"non_destructive": True})
    normalized.setdefault("verification_commands", [])
    if not normalized.get("workflow_id") and normalized.get("goal"):
        normalized["workflow_id"] = slugify(str(normalized["goal"]))[:80]
    return normalized


def command_is_obviously_dangerous(command: str) -> bool:
    text = " ".join(command.strip().lower().split())
    if not text:
        return False
    return any(pattern in text for pattern in DENIED_COMMAND_PATTERNS)


def command_has_known_safe_prefix(command: str) -> bool:
    text = command.strip().lower()
    return any(text.startswith(prefix) for prefix in SAFE_COMMAND_PREFIXES)


def validate_preflight_check(check: Any, index: int) -> list[str]:
    problems: list[str] = []
    if not isinstance(check, dict):
        return [f"preflight_checks[{index}] must be object"]

    check_id = str(check.get("id", "")).strip()
    if not check_id:
        problems.append(f"preflight_checks[{index}].id missing")

    command = str(check.get("command", "")).strip()
    if command:
        if command_is_obviously_dangerous(command):
            problems.append(f"preflight_checks[{index}].command dangerous: {command}")
    elif check.get("required") is True:
        problems.append(f"preflight_checks[{index}].command missing for required check")

    return problems


def validate_step(step: Any, index: int, known_ids: set[str]) -> list[str]:
    problems: list[str] = []
    if not isinstance(step, dict):
        return [f"steps[{index}] must be object"]

    step_id = str(step.get("id", "")).strip()
    if not step_id:
        problems.append(f"steps[{index}].id missing")
    elif step_id in known_ids:
        problems.append(f"steps[{index}].id duplicate: {step_id}")

    step_type = str(step.get("type", "")).strip()
    if step_type not in ALLOWED_STEP_TYPES:
        problems.append(
            f"steps[{index}].type must be one of {sorted(ALLOWED_STEP_TYPES)}"
        )

    depends_on = step.get("depends_on", [])
    if not isinstance(depends_on, list):
        problems.append(f"steps[{index}].depends_on must be list")

    expected_outputs = step.get("expected_outputs", [])
    if expected_outputs is not None and not isinstance(expected_outputs, list):
        problems.append(f"steps[{index}].expected_outputs must be list")

    if "parallelizable" in step and not isinstance(step.get("parallelizable"), bool):
        problems.append(f"steps[{index}].parallelizable must be boolean")

    return problems


def validate_workflow_spec(spec: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    if not isinstance(spec, dict):
        return ["spec must be object"]

    normalized = normalize_spec(spec)

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in normalized:
            problems.append(f"missing top-level field: {field}")

    if normalized.get("kind") != WORKFLOW_SPEC_KIND:
        problems.append("kind must be link_workflow_spec")

    if normalized.get("schema_version") != WORKFLOW_SPEC_SCHEMA_VERSION:
        problems.append("schema_version must be 1")

    workflow_id = str(normalized.get("workflow_id", "")).strip()
    if not workflow_id:
        problems.append("workflow_id missing")
    elif not re.fullmatch(r"[a-zA-Z0-9_.:-]+", workflow_id):
        problems.append("workflow_id contains unsupported characters")

    if not str(normalized.get("goal", "")).strip():
        problems.append("goal missing")

    if not isinstance(normalized.get("inputs"), dict):
        problems.append("inputs must be object")

    if not isinstance(normalized.get("required_tools"), list):
        problems.append("required_tools must be list")

    preflight_checks = normalized.get("preflight_checks")
    if not isinstance(preflight_checks, list):
        problems.append("preflight_checks must be list")
    else:
        for idx, check in enumerate(preflight_checks):
            problems.extend(validate_preflight_check(check, idx))

    steps = normalized.get("steps")
    step_ids: set[str] = set()
    if not isinstance(steps, list):
        problems.append("steps must be list")
    elif not steps:
        problems.append("steps must not be empty")
    else:
        for idx, step in enumerate(steps):
            before = set(step_ids)
            problems.extend(validate_step(step, idx, step_ids))
            if isinstance(step, dict) and step.get("id") and step.get("id") not in before:
                step_ids.add(str(step.get("id")))

        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            for dependency in step.get("depends_on", []) or []:
                if dependency not in step_ids:
                    problems.append(f"steps[{idx}] depends on unknown step: {dependency}")

    if not isinstance(normalized.get("expected_artifacts"), list):
        problems.append("expected_artifacts must be list")

    receipt_schema = normalized.get("receipt_schema")
    if not isinstance(receipt_schema, dict):
        problems.append("receipt_schema must be object")
    elif not receipt_schema.get("kind"):
        problems.append("receipt_schema.kind missing")

    rollback_policy = normalized.get("rollback_policy")
    if not isinstance(rollback_policy, dict):
        problems.append("rollback_policy must be object")
    elif rollback_policy.get("non_destructive") is not True:
        problems.append("rollback_policy.non_destructive must be true")

    verification_commands = normalized.get("verification_commands")
    if not isinstance(verification_commands, list):
        problems.append("verification_commands must be list")
    else:
        for idx, command in enumerate(verification_commands):
            command_text = str(command).strip()
            if not command_text:
                problems.append(f"verification_commands[{idx}] empty")
            elif command_is_obviously_dangerous(command_text):
                problems.append(f"verification_commands[{idx}] dangerous: {command_text}")

    return problems


def summarize_workflow_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_spec(spec)
    steps = normalized.get("steps") if isinstance(normalized.get("steps"), list) else []
    checks = (
        normalized.get("preflight_checks")
        if isinstance(normalized.get("preflight_checks"), list)
        else []
    )
    artifacts = (
        normalized.get("expected_artifacts")
        if isinstance(normalized.get("expected_artifacts"), list)
        else []
    )

    return {
        "kind": "link_workflow_spec_summary",
        "workflow_id": normalized.get("workflow_id"),
        "goal": normalized.get("goal"),
        "step_count": len(steps),
        "preflight_check_count": len(checks),
        "expected_artifact_count": len(artifacts),
        "verification_command_count": len(normalized.get("verification_commands", [])),
        "non_destructive": normalized.get("rollback_policy", {}).get("non_destructive") is True,
    }


def render_workflow_spec_html(spec: dict[str, Any]) -> str:
    normalized = normalize_spec(spec)
    summary = summarize_workflow_spec(normalized)

    workflow_id = html.escape(str(summary.get("workflow_id", "")))
    goal = html.escape(str(summary.get("goal", "")))
    step_count = html.escape(str(summary.get("step_count", 0)))
    preflight_count = html.escape(str(summary.get("preflight_check_count", 0)))

    items: list[str] = []
    for step in normalized.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_id = html.escape(str(step.get("id", "")))
        title = html.escape(str(step.get("title", "")))
        step_type = html.escape(str(step.get("type", "")))
        depends_on = ", ".join(str(x) for x in step.get("depends_on", []) or [])
        depends_on_html = html.escape(depends_on or "none")
        items.append(
            "<li>"
            f"<strong>{step_id}</strong> — {title or step_id}"
            f"<br>type: {step_type}"
            f"<br>depends_on: {depends_on_html}"
            "</li>"
        )

    if not items:
        items.append("<li>No steps recorded.</li>")

    return (
        '<section class="link-workflow-spec">'
        "<h2>Link workflow spec</h2>"
        f"<p>Workflow: <code>{workflow_id}</code></p>"
        f"<p>Goal: {goal}</p>"
        f"<p>Preflight checks: {preflight_count}</p>"
        f"<p>Steps: {step_count}</p>"
        "<ul>"
        + "".join(items)
        + "</ul>"
        "</section>"
    )


def load_workflow_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("workflow spec file must contain a JSON object")
    return normalize_spec(data)


def write_workflow_spec(path: Path, spec: dict[str, Any]) -> None:
    path.write_text(json.dumps(normalize_spec(spec), indent=2, sort_keys=True) + "\n")


def validate_link_workflow_spec_layer() -> list[str]:
    problems: list[str] = []

    sample = sample_workflow_spec()
    sample_problems = validate_workflow_spec(sample)
    if sample_problems:
        problems.extend(f"sample:{problem}" for problem in sample_problems)

    summary = summarize_workflow_spec(sample)
    if summary.get("step_count") != 3:
        problems.append("sample summary step count wrong")
    if summary.get("non_destructive") is not True:
        problems.append("sample summary must be non_destructive")

    html_card = render_workflow_spec_html(sample)
    if "Link workflow spec" not in html_card:
        problems.append("html render missing title")
    if "<form" in html_card.lower():
        problems.append("html render must not contain forms")

    bad = sample_workflow_spec()
    bad["verification_commands"] = ["git reset --hard HEAD"]
    bad_problems = validate_workflow_spec(bad)
    if not any("dangerous" in problem for problem in bad_problems):
        problems.append("dangerous verification command was not rejected")

    bad_dep = sample_workflow_spec()
    bad_dep["steps"][1]["depends_on"] = ["missing-step"]
    dep_problems = validate_workflow_spec(bad_dep)
    if not any("unknown step" in problem for problem in dep_problems):
        problems.append("unknown dependency was not rejected")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "workflow.json"
        write_workflow_spec(path, sample)
        loaded = load_workflow_spec(path)
        if loaded.get("workflow_id") != sample.get("workflow_id"):
            problems.append("roundtrip workflow_id mismatch")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and render Link workflow specs.")
    parser.add_argument("--file", help="Path to workflow spec JSON")
    parser.add_argument("--template", action="store_true", help="Print a sample workflow spec")
    parser.add_argument("--json", action="store_true", help="Print normalized JSON")
    parser.add_argument("--html", action="store_true", help="Print HTML card")
    parser.add_argument("--summary", action="store_true", help="Print workflow summary JSON")
    parser.add_argument("--self-test", action="store_true", help="Run built-in validation")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_link_workflow_spec_layer()
        if problems:
            print("workflow spec layer FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    spec = load_workflow_spec(Path(args.file)) if args.file else sample_workflow_spec()
    problems = validate_workflow_spec(spec)
    if problems:
        print("workflow spec validation FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    if args.html:
        print(render_workflow_spec_html(spec))
    elif args.summary:
        print(json.dumps(summarize_workflow_spec(spec), indent=2, sort_keys=True))
    else:
        print(json.dumps(normalize_spec(spec), indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
