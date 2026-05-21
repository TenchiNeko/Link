from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from factory.config import DEPARTMENTS, role_summary
from factory.models import WorkOrder, sanitize_project_name


ROOT = Path(__file__).resolve().parent
PROJECTS_DIR = ROOT / "projects"
WORK_ORDERS_DIR = ROOT / "work_orders"


def init_factory() -> None:
    for path in [
        PROJECTS_DIR,
        WORK_ORDERS_DIR,
        ROOT / "approvals",
        ROOT / "outputs",
        ROOT / "rejected_outputs",
        ROOT / "templates",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def project_dir(project: str) -> Path:
    return PROJECTS_DIR / sanitize_project_name(project)


def project_state_dir(project: str) -> Path:
    return project_dir(project) / "state"


def new_work_order_id(project: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{sanitize_project_name(project)}-{stamp}"


def plan(project: str, goal: str) -> str:
    init_factory()
    project = sanitize_project_name(project)
    state = project_state_dir(project)
    state.mkdir(parents=True, exist_ok=True)

    wo = WorkOrder(
        id=new_work_order_id(project),
        project=project,
        goal=goal,
        department="strategy",
        role="strategy_lead",
        inputs={
            "phase": "factory_phase_1",
            "departments": DEPARTMENTS,
            "roles": role_summary(),
            "execution_policy": "no model calls, no external actions, approval required",
        },
    )

    wo_path = state / "work_orders" / f"{wo.id}.json"
    wo.save(wo_path)
    wo.save(WORK_ORDERS_DIR / f"{wo.id}.json")

    plan_path = state / f"plan-{wo.id}.md"
    plan_path.write_text(
        "# Factory Plan\n\n"
        f"- project: `{project}`\n"
        f"- work_order: `{wo.id}`\n"
        f"- goal: {goal}\n"
        "- status: planned\n"
        "- execution: disabled in Phase 1\n"
        "- approval_required: true\n\n"
        "## Departments\n"
        + "\n".join(f"- {dept}" for dept in DEPARTMENTS)
        + "\n\n## Next step\n"
        "Review this plan, then create more specific work orders in a later phase.\n",
        encoding="utf-8",
    )

    return f"planned {wo.id}\nwork_order: {wo_path}\nplan: {plan_path}"


def run_today(project: str) -> str:
    init_factory()
    project = sanitize_project_name(project)
    state = project_state_dir(project)
    orders = sorted((state / "work_orders").glob("*.json")) if (state / "work_orders").exists() else []

    if not orders:
        return f"No work orders found for {project}. Run plan first."

    lines = [
        f"Factory run-today for {project}",
        "Phase 1 execution is disabled.",
        "No model calls, posting, publishing, or external actions will run.",
        "",
        "Queued work orders:",
    ]
    lines.extend(f"- {p.stem}" for p in orders)
    return "\n".join(lines)


def report(project: str) -> str:
    init_factory()
    project = sanitize_project_name(project)
    state = project_state_dir(project)
    orders = sorted((state / "work_orders").glob("*.json")) if (state / "work_orders").exists() else []

    lines = [
        f"Factory report for {project}",
        f"work_orders: {len(orders)}",
        "execution: disabled in Phase 1",
        "",
    ]

    for path in orders:
        wo = WorkOrder.load(path)
        lines.append(f"- {wo.id}: {wo.status} | {wo.department}/{wo.role} | approved={wo.approved}")

    return "\n".join(lines).rstrip()
