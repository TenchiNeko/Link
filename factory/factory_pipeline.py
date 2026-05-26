"""Factory pipeline orchestration.

Draft-only model collaboration:
- creates run folders
- calls role models only when explicitly executed
- passes each role output to the next role
- never posts/publishes externally
"""

from __future__ import annotations
import os
from factory.team_registry import tier_roles, FACTORY_TIERS

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .team_registry import PIPELINES, TEAM
from .assembly import assemble_factory_roles
from .openrouter_team import chat


ROOT = Path(__file__).resolve().parents[1]


def safe_project_name(value: str) -> str:
    value = value.strip().lower().replace("-", "_")
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise ValueError("empty project name")
    return value


def project_root(project: str) -> Path:
    return ROOT / "factory" / "projects" / safe_project_name(project)


def new_run_dir(project: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = project_root(project) / "runs" / stamp
    base.mkdir(parents=True, exist_ok=False)
    return base


def _compact_context(outputs: list[dict[str, Any]], limit: int = 9000) -> str:
    chunks = []
    for item in outputs[-8:]:
        chunks.append(
            f"## Previous role: {item['role_id']} / {item['title']}\n"
            f"{item['content'][:2500]}"
        )
    text = "\n\n".join(chunks)
    return text[-limit:]


def _role_user_prompt(project: str, goal: str, role_id: str, previous_outputs: list[dict[str, Any]]) -> str:
    role = TEAM[role_id]
    context = _compact_context(previous_outputs)
    return f"""Project: {project}

Main goal:
{goal}

Your factory position:
- role_id: {role.role_id}
- title: {role.title}
- department: {role.department}
- objective: {role.objective}
- handoff_to: {', '.join(role.handoff_to) if role.handoff_to else 'final'}

Previous factory context:
{context if context else '[No previous outputs yet.]'}

Instructions:
1. Do only your assigned role.
2. Produce draft-only work.
3. Do not claim anything was posted, published, sent, bought, scraped, or deployed.
4. End with a short "HANDOFF" section telling the next role what to use.
"""


def run_pipeline(
    *,
    project: str,
    goal: str,
    tier: str = "cheap",
    execute_models: bool = False,
    max_tokens: int = 1600,
) -> dict[str, Any]:
    os.environ["LINK_FACTORY_ACTIVE_PROJECT"] = str(project)
    assembly = None
    if tier == "auto":
        assembly = assemble_factory_roles(project=project, goal=goal)
        roles = list(assembly.roles)
    else:
        if tier not in PIPELINES:
            raise ValueError(f"unknown tier {tier!r}; expected one of {sorted(set(PIPELINES) | {'auto'})}")
        roles = list(PIPELINES[tier])
    if assembly is not None:
        manifest["assembly"] = assembly.as_dict()

    outputs: list[dict[str, Any]] = []

    manifest = {
        "schema": "factory_run_v1",
        "project": safe_project_name(project),
        "goal": goal,
        "tier": tier,
        "execute_models": execute_models,
        "run_dir": str(run_dir),
        "roles": roles,
        "outputs": [],
        "policy": {
            "external_posting": False,
            "publishing": False,
            "human_approval_required": True,
        },
    }

    for idx, role_id in enumerate(roles, start=1):
        role = TEAM[role_id]
        user_prompt = _role_user_prompt(project, goal, role_id, outputs)

        if execute_models:
            reply = chat(
                model=role.model,
                system=role.system_prompt,
                user=user_prompt,
                max_tokens=max_tokens,
            )
            content = reply.content
            usage = reply.usage
        else:
            content = (
                f"[DRY RUN]\n"
                f"Would call model: {role.model}\n"
                f"Role: {role.title}\n"
                f"Department: {role.department}\n"
                f"Objective: {role.objective}\n\n"
                f"HANDOFF:\nThis would be passed to: {', '.join(role.handoff_to) if role.handoff_to else 'final'}"
            )
            usage = {}

        item = {
            "index": idx,
            "role_id": role_id,
            "title": role.title,
            "department": role.department,
            "model": role.model,
            "content": content,
            "usage": usage,
        }
        outputs.append(item)
        manifest["outputs"].append({k: v for k, v in item.items() if k != "content"})

        out_file = run_dir / f"{idx:02d}-{role_id}.md"
        out_file.write_text(
            f"# {idx:02d} - {role.title}\n\n"
            f"- department: `{role.department}`\n"
            f"- model: `{role.model}`\n\n"
            f"{content}\n",
            encoding="utf-8",
        )

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary_path = run_dir / "SUMMARY.md"
    summary_path.write_text(
        "# Factory Run Summary\n\n"
        f"- project: `{safe_project_name(project)}`\n"
        f"- tier: `{tier}`\n"
        f"- execute_models: `{execute_models}`\n"
        f"- roles: `{len(roles)}`\n\n"
        "## Files\n\n"
        + "\n".join(f"- `{i:02d}-{role_id}.md`" for i, role_id in enumerate(roles, start=1))
        + "\n",
        encoding="utf-8",
    )

    return {
        "run_dir": str(run_dir),
        "manifest": str(manifest_path),
        "summary": str(summary_path),
        "roles": roles,
        "execute_models": execute_models,
    }

# Registry-backed tier map override.
try:
    PIPELINES = FACTORY_TIERS
except NameError:
    pass
