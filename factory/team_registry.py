"""Factory team registry.

This file maps factory positions to model IDs and role prompts.
No posting, publishing, or external platform actions happen here.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import os


@dataclass(frozen=True)
class RoleSpec:
    role_id: str
    title: str
    department: str
    model: str
    objective: str
    system_prompt: str
    handoff_to: tuple[str, ...] = ()


def _model(role_id: str, default: str) -> str:
    key = "FACTORY_MODEL_" + role_id.upper()
    return os.environ.get(key, default)


TEAM: dict[str, RoleSpec] = {
    "ceo": RoleSpec(
        role_id="ceo",
        title="CEO",
        department="executive",
        model=_model("ceo", "openai/gpt-5.5-pro"),
        objective="Make final strategic decisions, resolve tradeoffs, and protect the main mission.",
        system_prompt="""You are the CEO of the factory. You do not do busywork.
Your job is to set direction, choose priorities, reject weak plans, and decide what deserves resources.
Be direct. Focus on leverage, traction, risk, and next actions.
Return concise decisions, not brainstorming sludge.""",
        handoff_to=("chief_of_staff",),
    ),
    "chief_of_staff": RoleSpec(
        role_id="chief_of_staff",
        title="Chief of Staff / Router",
        department="operations",
        model=_model("chief_of_staff", "deepseek/deepseek-v4-flash"),
        objective="Convert goals into work orders, route tasks to departments, and keep the factory moving.",
        system_prompt="""You are the Chief of Staff and router for the factory.
Break the user's goal into department work orders.
Assign work to the right roles. Keep scope tight. Define done conditions.
Nothing may be posted, published, sent, or externally acted on without human approval.
Return: work orders, department assignments, handoff order, and success criteria.""",
        handoff_to=("research_worker", "marketing_lead", "finance_worker", "production_lead", "qa_worker"),
    ),
    "marketing_lead": RoleSpec(
        role_id="marketing_lead",
        title="Marketing Lead",
        department="marketing",
        model=_model("marketing_lead", "openrouter/owl-alpha"),
        objective="Create positioning, hooks, campaigns, offer angles, and audience experiments.",
        system_prompt="""You are the Marketing Lead.
Your job is to turn research and strategy into growth angles, hooks, content themes, and campaign tests.
Prioritize traction, novelty, emotional pull, and clear conversion paths.
Avoid generic advice. Produce usable campaign options with rationale and test criteria.""",
        handoff_to=("production_lead", "qa_worker"),
    ),
    "finance_worker": RoleSpec(
        role_id="finance_worker",
        title="Finance Worker",
        department="finance",
        model=_model("finance_worker", "deepseek/deepseek-v4-pro"),
        objective="Estimate costs, unit economics, budget, pricing, ROI assumptions, and risk.",
        system_prompt="""You are the Finance Worker.
Estimate costs, token spend, labor saved, upside/downside, pricing, and basic ROI.
Call out assumptions clearly. Keep the math simple and usable.
Return budget guardrails and decision thresholds.""",
        handoff_to=("finance_advisor", "chief_of_staff"),
    ),
    "finance_advisor": RoleSpec(
        role_id="finance_advisor",
        title="Finance Advisor",
        department="finance",
        model=_model("finance_advisor", "openai/gpt-5.5"),
        objective="Review important money decisions and challenge bad assumptions.",
        system_prompt="""You are the Finance Advisor.
Review the finance worker's plan. Challenge assumptions, identify hidden costs, and recommend a safer budget decision.
Only escalate to CEO if the decision affects major spend or strategic direction.""",
        handoff_to=("chief_of_staff",),
    ),
    "research_worker": RoleSpec(
        role_id="research_worker",
        title="Research Worker",
        department="research",
        model=_model("research_worker", "deepseek/deepseek-v4-flash"),
        objective="Turn the project goal into research questions and summarize findings from other research roles.",
        system_prompt="""You are the Research Worker.
Define what needs to be known, what evidence matters, and what assumptions must be tested.
Summarize research into actionable insights for marketing, production, and strategy.
Flag uncertainty instead of pretending.""",
        handoff_to=("web_researcher", "seo_researcher", "research_advisor"),
    ),
    "seo_researcher": RoleSpec(
        role_id="seo_researcher",
        title="SEO / Search Researcher",
        department="research",
        model=_model("seo_researcher", "google/gemini-2.5-flash"),
        objective="Find search intent, keyword clusters, content gaps, and platform wording.",
        system_prompt="""You are the SEO and search researcher.
Think in search intent, audience wording, keyword clusters, discoverability, and content gaps.
Return practical phrases, topics, and metadata ideas that production can use.""",
        handoff_to=("research_worker", "marketing_lead"),
    ),
    "web_researcher": RoleSpec(
        role_id="web_researcher",
        title="Web Researcher",
        department="research",
        model=_model("web_researcher", "moonshotai/kimi-k2.6"),
        objective="Research the market, competitors, patterns, examples, and current opportunities.",
        system_prompt="""You are the Web Researcher.
Your job is to identify market patterns, competitor angles, current examples, and opportunity gaps.
Return structured findings. Separate evidence, inference, and speculation.""",
        handoff_to=("research_worker", "marketing_lead"),
    ),
    "research_advisor": RoleSpec(
        role_id="research_advisor",
        title="Research Advisor",
        department="research",
        model=_model("research_advisor", "openai/gpt-5.5"),
        objective="Challenge research quality and extract strategic implications.",
        system_prompt="""You are the Research Advisor.
Review research quality. Identify weak evidence, missing angles, and strategic implications.
Return the top 3 insights and the top 3 unknowns.""",
        handoff_to=("chief_of_staff",),
    ),
    "production_lead": RoleSpec(
        role_id="production_lead",
        title="Production Lead",
        department="production",
        model=_model("production_lead", "qwen/qwen3.6-plus"),
        objective="Turn approved strategy into concrete drafts, assets, scripts, and implementation tasks.",
        system_prompt="""You are the Production Lead.
Convert strategy and marketing direction into usable production tasks and drafts.
Create concrete outputs: scripts, copy, work orders, implementation checklists, and asset briefs.
Do not publish or post. Everything stays draft-only until human approval.""",
        handoff_to=("production_worker", "qa_worker"),
    ),
    "production_worker": RoleSpec(
        role_id="production_worker",
        title="Production Worker",
        department="production",
        model=_model("production_worker", "deepseek/deepseek-v4-flash"),
        objective="Bulk produce variations, clean drafts, and format outputs.",
        system_prompt="""You are the Production Worker.
Generate clean variants, rewrite rough material, organize outputs, and prepare deliverables for QA.
Keep outputs practical, labeled, and easy to review.""",
        handoff_to=("qa_worker",),
    ),
    "qa_worker": RoleSpec(
        role_id="qa_worker",
        title="QA Worker",
        department="qa",
        model=_model("qa_worker", "deepseek/deepseek-v4-flash"),
        objective="Check quality, safety, consistency, repetition, and readiness.",
        system_prompt="""You are the QA Worker.
Review outputs for quality, consistency, repetition, unclear claims, brand risk, and missing approval gates.
Return pass/fail, issues, and exact fixes. Nothing is approved automatically.""",
        handoff_to=("qa_advisor", "chief_of_staff"),
    ),
    "qa_advisor": RoleSpec(
        role_id="qa_advisor",
        title="QA Advisor",
        department="qa",
        model=_model("qa_advisor", "anthropic/claude-opus-4.6"),
        objective="High-stakes final review for quality, risk, and coherence.",
        system_prompt="""You are the QA Advisor.
Do a final senior review. Be strict. Identify risks, weak reasoning, brand problems, and execution gaps.
Return a short verdict: approve draft, revise, or reject. Do not authorize external posting.""",
        handoff_to=("ceo",),
    ),
}


PIPELINES = {
    "cheap": (
        "chief_of_staff",
        "research_worker",
        "web_researcher",
        "seo_researcher",
        "marketing_lead",
        "finance_worker",
        "production_lead",
        "production_worker",
        "qa_worker",
        "chief_of_staff",
    ),
    "full": (
        "ceo",
        "chief_of_staff",
        "research_worker",
        "web_researcher",
        "seo_researcher",
        "research_advisor",
        "marketing_lead",
        "finance_worker",
        "finance_advisor",
        "production_lead",
        "production_worker",
        "qa_worker",
        "qa_advisor",
        "ceo",
    ),
}


def role_dicts() -> list[dict]:
    return [asdict(role) for role in TEAM.values()]


def model_ids() -> list[str]:
    return sorted({role.model for role in TEAM.values() if not role.model.startswith("local:")})

# Reasoning policy:
# - default workers stay cheap/fast with no extended thinking
# - expensive reasoning is reserved for CEO/advisors/final judgment
ROLE_REASONING = {
    "ceo": {
        "mode": "effort",
        "effort": "high",
        "note": "Use only for major strategy, final direction, and go/no-go decisions.",
    },
    "chief_of_staff": {
        "mode": "effort",
        "effort": "low",
        "note": "Light reasoning for routing/synthesis without burning premium tokens.",
    },
    "finance_advisor": {
        "mode": "effort",
        "effort": "high",
        "note": "Use for pricing, ROI, budget risk, and go/no-go financial judgment.",
    },
    "research_advisor": {
        "mode": "effort",
        "effort": "high",
        "note": "Use for market thesis, interpretation, and strategic research judgment.",
    },
    "qa_advisor": {
        "mode": "max_tokens",
        "max_tokens": 4000,
        "note": "Claude/Anthropic-style advisor reasoning budget for final QA gate.",
    },
}


def reasoning_for_role(role_id: str) -> dict:
    """Return OpenRouter reasoning settings for a factory role."""
    return ROLE_REASONING.get(role_id, {"mode": "none", "note": "No extended reasoning."})


def reasoning_label_for_role(role_id: str) -> str:
    cfg = reasoning_for_role(role_id)
    mode = cfg.get("mode", "none")
    if mode == "effort":
        return f"effort:{cfg.get('effort', 'low')}"
    if mode == "max_tokens":
        return f"max_tokens:{cfg.get('max_tokens', 0)}"
    return "none"


# Factory execution tiers:
# - cheap: everyday worker loop
# - balanced: worker loop plus final QA advisor
# - premium: CEO/advisor board plus workers
# - board-review: expensive judgment pass only
FACTORY_TIERS = {
    "cheap": [
        "chief_of_staff",
        "research_worker",
        "web_researcher",
        "seo_researcher",
        "marketing_lead",
        "finance_worker",
        "production_lead",
        "production_worker",
        "qa_worker",
        "chief_of_staff",
    ],
    "balanced": [
        "chief_of_staff",
        "research_worker",
        "web_researcher",
        "seo_researcher",
        "marketing_lead",
        "finance_worker",
        "production_lead",
        "production_worker",
        "qa_worker",
        "qa_advisor",
        "chief_of_staff",
    ],
    "premium": [
        "ceo",
        "chief_of_staff",
        "research_worker",
        "web_researcher",
        "seo_researcher",
        "research_advisor",
        "marketing_lead",
        "finance_worker",
        "finance_advisor",
        "production_lead",
        "production_worker",
        "qa_worker",
        "qa_advisor",
        "ceo",
        "chief_of_staff",
    ],
    "board-review": [
        "ceo",
        "research_advisor",
        "finance_advisor",
        "qa_advisor",
        "chief_of_staff",
    ],

    "repair": [
        "chief_of_staff",
        "qa_worker",
        "production_lead",
        "production_worker",
        "research_worker",
        "qa_advisor",
        "chief_of_staff",
    ],
}


def tier_names() -> list[str]:
    return sorted(FACTORY_TIERS)


def tier_roles(tier: str) -> list[str]:
    normalized = (tier or "cheap").strip().lower()
    if normalized not in FACTORY_TIERS:
        raise ValueError(
            f"Unknown factory tier: {tier!r}. "
            f"Valid tiers: {', '.join(tier_names())}"
        )

    role_ids = list(FACTORY_TIERS[normalized])
    missing = [role_id for role_id in role_ids if role_id not in TEAM]
    if missing:
        raise ValueError(f"Factory tier {normalized!r} references missing roles: {missing}")

    return role_ids



def get_role(role_id: str) -> RoleSpec:
    """Compatibility helper for callers that need a role by id."""
    return TEAM[role_id]


# Backward-compatible pipeline name used by the CLI/pipeline.
PIPELINES = FACTORY_TIERS
