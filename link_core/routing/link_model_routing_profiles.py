#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ROUTING_RECEIPT_VERSION = "LU93-model-routing-profiles-v1"


@dataclass(frozen=True)
class ModelRoutingProfile:
    name: str
    provider: str
    model_env: str
    default_model: str
    endpoint_env: str
    endpoint_default: str
    priority: int
    use_cases: list[str] = field(default_factory=list)
    fallback_profile: str = ""
    requires_api_key_env: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ROUTING_PROFILES: tuple[ModelRoutingProfile, ...] = (
    ModelRoutingProfile(
        name="local_fast",
        provider="ollama",
        model_env="LINK_LOCAL_FAST_MODEL",
        default_model="qwen2.5-coder:32b-instruct-q8_0",
        endpoint_env="OLLAMA_BASE_URL",
        endpoint_default="http://127.0.0.1:11434",
        priority=10,
        use_cases=["triage", "small patches", "fast local checks", "status summaries"],
        fallback_profile="local_deep",
        notes="Default fast local route for low-latency repo work.",
    ),
    ModelRoutingProfile(
        name="local_deep",
        provider="ollama",
        model_env="LINK_LOCAL_DEEP_MODEL",
        default_model="qwen2.5:32b",
        endpoint_env="OLLAMA_BASE_URL",
        endpoint_default="http://127.0.0.1:11434",
        priority=20,
        use_cases=["deep local reasoning", "offline coding", "privacy-sensitive review"],
        fallback_profile="cloud_deep",
        notes="Local deep route when privacy or offline operation matters.",
    ),
    ModelRoutingProfile(
        name="cloud_deep",
        provider="openrouter",
        model_env="OPENROUTER_MODEL",
        default_model="deepseek/deepseek-chat",
        endpoint_env="OPENROUTER_BASE_URL",
        endpoint_default="https://openrouter.ai/api",
        priority=30,
        use_cases=["hard reasoning", "large context", "cloud fallback", "model comparison"],
        fallback_profile="local_deep",
        requires_api_key_env="OPENROUTER_API_KEY",
        notes="Cloud route for tasks that exceed local model strength or context.",
    ),
    ModelRoutingProfile(
        name="hybrid_fallback",
        provider="router",
        model_env="LINK_ROUTER_MODE",
        default_model="auto",
        endpoint_env="",
        endpoint_default="",
        priority=40,
        use_cases=["automatic fallback", "mixed local/cloud routing", "resilient execution"],
        fallback_profile="local_fast",
        notes="Policy profile for choosing local first, then cloud when explicitly allowed.",
    ),
)


def profile_map() -> dict[str, ModelRoutingProfile]:
    return {profile.name: profile for profile in ROUTING_PROFILES}


def get_profile(name: str) -> ModelRoutingProfile:
    profiles = profile_map()
    key = str(name or "").strip()
    if key not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"unknown model routing profile: {key}. Available profiles: {available}")
    return profiles[key]


def fallback_chain(name: str, limit: int = 8) -> list[str]:
    profiles = profile_map()
    chain: list[str] = []
    seen: set[str] = set()
    current = name

    for _ in range(limit):
        profile = profiles.get(current)
        if not profile or not profile.fallback_profile:
            break
        nxt = profile.fallback_profile
        if nxt in seen:
            chain.append(f"{nxt}:cycle")
            break
        chain.append(nxt)
        seen.add(nxt)
        current = nxt

    return chain


def profile_summary(name: str) -> dict[str, Any]:
    profile = get_profile(name)
    return {
        "receipt_version": ROUTING_RECEIPT_VERSION,
        "profile": profile.to_dict(),
        "fallback_chain": fallback_chain(profile.name),
    }


def all_profile_summaries() -> dict[str, Any]:
    return {
        "receipt_version": ROUTING_RECEIPT_VERSION,
        "profiles": [profile_summary(profile.name) for profile in ROUTING_PROFILES],
        "validation": validate_model_routing_profiles(),
    }


def validate_model_routing_profiles() -> dict[str, Any]:
    names = [profile.name for profile in ROUTING_PROFILES]
    providers = {"ollama", "openrouter", "router"}

    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    invalid_providers = sorted(
        profile.name for profile in ROUTING_PROFILES if profile.provider not in providers
    )
    missing_models = sorted(
        profile.name for profile in ROUTING_PROFILES if not profile.model_env or not profile.default_model
    )
    unknown_fallbacks = sorted(
        f"{profile.name}:{profile.fallback_profile}"
        for profile in ROUTING_PROFILES
        if profile.fallback_profile and profile.fallback_profile not in names
    )

    priority_values = [profile.priority for profile in ROUTING_PROFILES]
    duplicate_priorities = sorted(
        {value for value in priority_values if priority_values.count(value) > 1}
    )

    ok = not duplicate_names and not invalid_providers and not missing_models and not unknown_fallbacks and not duplicate_priorities

    return {
        "ok": ok,
        "profile_count": len(ROUTING_PROFILES),
        "duplicate_names": duplicate_names,
        "invalid_providers": invalid_providers,
        "missing_models": missing_models,
        "unknown_fallbacks": unknown_fallbacks,
        "duplicate_priorities": duplicate_priorities,
        "profile_names": names,
    }


def select_routing_profile(
    goal: str,
    *,
    prefer_local: bool = False,
    prefer_cloud: bool = False,
    require_deep: bool = False,
) -> dict[str, Any]:
    text = str(goal or "").lower()

    local_terms = ("local", "offline", "ollama", "privacy", "private")
    cloud_terms = ("cloud", "openrouter", "api", "large context")
    fast_terms = ("fast", "triage", "small", "quick", "status", "summary")
    deep_terms = ("deep", "hard", "reason", "complex", "research", "large")

    if prefer_cloud or any(term in text for term in cloud_terms):
        selected = "cloud_deep"
    elif prefer_local or any(term in text for term in local_terms):
        selected = "local_deep" if require_deep or any(term in text for term in deep_terms) else "local_fast"
    elif require_deep or any(term in text for term in deep_terms):
        selected = "local_deep"
    elif any(term in text for term in fast_terms):
        selected = "local_fast"
    else:
        selected = "hybrid_fallback"

    profile = get_profile(selected)

    return {
        "receipt_version": ROUTING_RECEIPT_VERSION,
        "goal": goal,
        "selected_profile": selected,
        "provider": profile.provider,
        "model_env": profile.model_env,
        "default_model": profile.default_model,
        "endpoint_env": profile.endpoint_env,
        "endpoint_default": profile.endpoint_default,
        "requires_api_key_env": profile.requires_api_key_env,
        "fallback_chain": fallback_chain(selected),
        "reason": "deterministic keyword/profile routing; no network call was made",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if "selected_profile" in payload:
        lines = [
            "# Link Model Routing Decision",
            "",
            f"Goal: {payload.get('goal', '')}",
            f"Selected profile: **{payload['selected_profile']}**",
            f"Provider: `{payload['provider']}`",
            f"Model env: `{payload['model_env']}`",
            f"Default model: `{payload['default_model']}`",
            f"Endpoint env: `{payload['endpoint_env']}`",
            f"Fallback chain: " + ", ".join(f"`{x}`" for x in payload.get("fallback_chain", [])),
            "",
            f"Reason: {payload['reason']}",
        ]
        return "\n".join(lines).strip() + "\n"

    if "profile" in payload:
        profile = payload["profile"]
        lines = [
            "# Link Model Routing Profile",
            "",
            f"Name: **{profile['name']}**",
            f"Provider: `{profile['provider']}`",
            f"Default model: `{profile['default_model']}`",
            f"Fallback chain: " + ", ".join(f"`{x}`" for x in payload.get("fallback_chain", [])),
            "",
            "## Use Cases",
        ]
        lines.extend(f"- {item}" for item in profile.get("use_cases", []))
        return "\n".join(lines).strip() + "\n"

    lines = ["# Link Model Routing Profiles", ""]
    for item in payload.get("profiles", []):
        profile = item["profile"]
        lines.append(f"- **{profile['name']}** — `{profile['provider']}` / `{profile['default_model']}`")
    lines.append("")
    lines.append(f"Validation OK: **{payload.get('validation', {}).get('ok')}**")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect deterministic Link model routing profiles.")
    parser.add_argument("--profile", default="", help="Show one routing profile.")
    parser.add_argument("--goal", default="", help="Select a routing profile for a goal.")
    parser.add_argument("--prefer-local", action="store_true")
    parser.add_argument("--prefer-cloud", action="store_true")
    parser.add_argument("--require-deep", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    if args.validate:
        payload = validate_model_routing_profiles()
    elif args.profile:
        payload = profile_summary(args.profile)
    elif args.goal or args.prefer_local or args.prefer_cloud or args.require_deep:
        payload = select_routing_profile(
            args.goal,
            prefer_local=args.prefer_local,
            prefer_cloud=args.prefer_cloud,
            require_deep=args.require_deep,
        )
    else:
        payload = all_profile_summaries()

    if args.format == "markdown":
        print(render_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
