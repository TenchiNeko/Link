"""Canonical Link role definitions facade.

Import path: ``link_core.roles``

Link has two complementary notions of "role":

1. Business/factory roles (CEO, chief of staff, research, marketing, QA, ...)
   defined in ``factory.team_registry``. These describe the multi-agent
   business operations team.

2. Worker safety profiles (research_only, patch_worker, qa_worker, ...)
   defined in ``link_core.routing.link_worker_profiles``. These restrict which
   tools a worker may use.

This module is a thin facade that exposes both under one canonical import,
without changing behavior. It performs no execution and grants no permissions;
profiles still narrow tools and the capability gate still governs execution.
"""

from __future__ import annotations

from typing import Any

# --- Business / factory team roles -----------------------------------------
try:  # pragma: no cover - defensive import
    from factory.team_registry import (
        TEAM as BUSINESS_TEAM,
        RoleSpec as BusinessRoleSpec,
        get_role as get_business_role,
        role_dicts as business_role_dicts,
        tier_names as business_tier_names,
        tier_roles as business_tier_roles,
    )
except Exception:  # pragma: no cover
    BUSINESS_TEAM = {}  # type: ignore[assignment]
    BusinessRoleSpec = None  # type: ignore[assignment]
    get_business_role = None  # type: ignore[assignment]
    business_role_dicts = None  # type: ignore[assignment]
    business_tier_names = None  # type: ignore[assignment]
    business_tier_roles = None  # type: ignore[assignment]

# --- Worker safety profiles -------------------------------------------------
from link_core.routing.link_worker_profiles import (
    PROFILES as WORKER_PROFILES,
    WorkerProfile,
    get_profile as get_worker_profile,
    list_profiles as list_worker_profiles,
    profile_summary as worker_profile_summary,
    resolve_profile_tools as resolve_worker_profile_tools,
    validate_profiles as validate_worker_profiles,
)


def list_business_roles() -> list[dict[str, Any]]:
    """Return business/factory role definitions as plain dicts."""
    if business_role_dicts is None:
        return []
    return business_role_dicts()


def list_worker_profile_names() -> list[str]:
    """Return the names of all worker safety profiles."""
    return [profile.name for profile in WORKER_PROFILES]


__all__ = [
    # business / factory roles
    "BUSINESS_TEAM",
    "BusinessRoleSpec",
    "get_business_role",
    "business_role_dicts",
    "business_tier_names",
    "business_tier_roles",
    "list_business_roles",
    # worker safety profiles
    "WORKER_PROFILES",
    "WorkerProfile",
    "get_worker_profile",
    "list_worker_profiles",
    "worker_profile_summary",
    "resolve_worker_profile_tools",
    "validate_worker_profiles",
    "list_worker_profile_names",
]
