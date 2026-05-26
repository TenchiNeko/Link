"""Dynamic factory role assembly.

Assembles a job-shaped factory crew from project, goal, and task signals.
This keeps factory execution preset-driven but not static.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FactoryAssembly:
    preset: str
    roles: list[str]
    reason: str
    signals: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _available_roles() -> set[str]:
    try:
        from factory.team_registry import TEAM
        return set(TEAM)
    except Exception:
        return set()


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _filter_available(role_ids: Iterable[str], available: set[str]) -> list[str]:
    roles = _dedupe_keep_order(role_ids)
    if not available:
        return roles
    return [role for role in roles if role in available]


def _task_text(project: str, goal: str, task: Mapping[str, Any] | None = None) -> str:
    parts = [project, goal]
    if task:
        for key in ("task_id", "title", "why", "risk", "status", "source_draft_id"):
            value = task.get(key)
            if value:
                parts.append(str(value))
        for key in ("files", "plan", "tests", "safety"):
            value = task.get(key)
            if isinstance(value, list):
                parts.extend(str(x) for x in value)
    return " ".join(parts).lower()


def assemble_factory_roles(
    project: str,
    goal: str,
    task: Mapping[str, Any] | None = None,
    available_roles: Iterable[str] | None = None,
) -> FactoryAssembly:
    available = set(available_roles or _available_roles())
    text = _task_text(project, goal, task)

    is_link = "link" in text or "link_" in text or ".link" in text
    is_code = any(x in text for x in (
        "implement", "patch", "code", ".py", "healthcheck", "compile",
        "runner", "adapter", "pipeline", "dashboard", "queue", "bridge",
    ))
    is_research = any(x in text for x in (
        "research", "evidence", "market", "context", "source", "scanner",
        "inventory", "refresh", "rubric",
    ))
    is_growth = any(x in text for x in (
        "growth", "funnel", "creative", "content", "social", "seo",
        "analytics", "campaign", "audience",
    ))
    is_finance = any(x in text for x in (
        "finance", "pricing", "revenue", "cost", "budget",
    ))
    is_high_risk = any(x in text for x in (
        "high", "risky", "protected", "approval", "guarded",
    ))

    signals: list[str] = []
    roles: list[str]

    if is_link and is_code:
        signals.extend(["link_project", "code_implementation"])
        roles = [
            "chief_of_staff",
            "research_worker" if is_research else "",
            "web_researcher" if is_research else "",
            "production_lead",
            "production_worker",
            "qa_worker",
            "chief_of_staff",
        ]
        preset = "link_implementation"
        reason = "Link/code job detected; assemble planner, implementer, context researcher, and QA."

    elif is_growth:
        signals.append("growth_project")
        roles = [
            "chief_of_staff",
            "research_worker",
            "web_researcher",
            "marketing_lead",
            "production_lead",
            "production_worker",
            "qa_worker",
            "chief_of_staff",
        ]
        preset = "growth_lab"
        reason = "Growth job detected; assemble research, positioning, production, and QA."

    elif is_research:
        signals.append("research_project")
        roles = [
            "chief_of_staff",
            "research_worker",
            "web_researcher",
            "production_worker",
            "qa_worker",
            "chief_of_staff",
        ]
        preset = "research_report"
        reason = "Research-heavy job detected; assemble research, synthesis, and QA."

    elif is_finance:
        signals.append("finance_project")
        roles = [
            "chief_of_staff",
            "research_worker",
            "finance_worker",
            "qa_worker",
            "chief_of_staff",
        ]
        preset = "finance_analysis"
        reason = "Finance/pricing job detected; assemble analysis and QA."

    else:
        signals.append("general_project")
        roles = [
            "chief_of_staff",
            "research_worker",
            "production_worker",
            "qa_worker",
            "chief_of_staff",
        ]
        preset = "general_factory"
        reason = "No narrow preset matched; assemble compact general-purpose team."

    if is_high_risk:
        signals.append("approval_or_high_risk")
        roles = ["chief_of_staff", *roles, "qa_worker", "chief_of_staff"]

    selected = _filter_available(roles, available)
    if not selected:
        selected = ["chief_of_staff", "research_worker", "production_worker", "qa_worker"]

    return FactoryAssembly(
        preset=preset,
        roles=selected,
        reason=reason,
        signals=_dedupe_keep_order(signals),
    )
