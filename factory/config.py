from __future__ import annotations

import os
from dataclasses import dataclass


DEPARTMENTS = [
    "strategy",
    "market_research",
    "model_incubator",
    "creative_production",
    "growth",
    "qa",
    "analytics",
]


@dataclass(frozen=True)
class RoleSpec:
    name: str
    department: str
    description: str
    model_env: str
    default_model: str = "openrouter/auto"

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env, self.default_model)


ROLE_REGISTRY: dict[str, RoleSpec] = {
    "strategy_lead": RoleSpec(
        name="strategy_lead",
        department="strategy",
        description="Turns a goal into a project plan and assigns departments.",
        model_env="FACTORY_STRATEGY_MODEL",
    ),
    "market_researcher": RoleSpec(
        name="market_researcher",
        department="market_research",
        description="Researches audience, competitors, offers, and trends.",
        model_env="FACTORY_RESEARCH_MODEL",
    ),
    "marketing_specialist": RoleSpec(
        name="marketing_specialist",
        department="growth",
        description="Creates hooks, angles, positioning, and growth experiments.",
        model_env="FACTORY_MARKETING_MODEL",
    ),
    "creative_director": RoleSpec(
        name="creative_director",
        department="creative_production",
        description="Creates content briefs, creative directions, and asset plans.",
        model_env="FACTORY_CREATIVE_MODEL",
    ),
    "qa_reviewer": RoleSpec(
        name="qa_reviewer",
        department="qa",
        description="Reviews outputs for quality, safety, and approval readiness.",
        model_env="FACTORY_QA_MODEL",
    ),
    "analytics_lead": RoleSpec(
        name="analytics_lead",
        department="analytics",
        description="Reviews results and recommends next experiments.",
        model_env="FACTORY_ANALYTICS_MODEL",
    ),
}


def get_role(name: str) -> RoleSpec:
    if name not in ROLE_REGISTRY:
        raise KeyError(f"Unknown factory role: {name}")
    return ROLE_REGISTRY[name]


def role_summary() -> list[dict[str, str]]:
    return [
        {
            "name": role.name,
            "department": role.department,
            "model_env": role.model_env,
            "model": role.model,
            "description": role.description,
        }
        for role in ROLE_REGISTRY.values()
    ]
