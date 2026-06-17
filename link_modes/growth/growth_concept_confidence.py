"""Concept-confidence calibration subsystem for Growth.

Extracted from ``link_growth_console.py``.  This module owns deterministic
concept confidence calibration helpers.  Source concept collection and repo-role
classification are supplied by callbacks so the module does not import the
Growth monolith.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

CONCEPT_CONFIDENCE_CALIBRATION_VERSION = "link-concept-confidence-calibration-v1"

ArchiveConceptCollector = Callable[..., dict[str, Any]]
ArchiveConceptValidator = Callable[[dict[str, Any]], None]
RepoRoleCollector = Callable[..., dict[str, Any]]
RepoRoleValidator = Callable[[dict[str, Any], dict[str, Any] | None], None]


def _stable_json(value: Any, indent: int | None = None) -> str:
    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return json.dumps(value, **kwargs)


def _hash_text(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read_only_safety_metadata() -> dict[str, Any]:
    return {
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "writes": [],
    }


def concept_confidence_label(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 35:
        return "weak"
    return "low"


def role_supports_concept(primary_role: str, concept_family: str) -> bool:
    supported = {
        "compression_context": {"compression", "rag", "cli", "library", "mcp", "proxy"},
        "crawler_source_collection": {"crawler", "scraper", "data_pipeline"},
        "business_reach_outreach": {"business_growth", "workflow_automation"},
        "workflow_automation": {"workflow_automation", "data_pipeline", "api_server"},
        "ai_workflow_builder": {"workflow_automation", "dashboard_ui", "chatbot", "api_server", "data_pipeline"},
        "agent_memory_retrieval": {"agent_memory", "rag", "data_pipeline"},
        "chatbot_companion": {"chatbot", "api_server", "dashboard_ui"},
        "dashboard_ui": {"dashboard_ui"},
        "api_server": {"api_server"},
        "data_pipeline": {"data_pipeline"},
    }
    return concept_family in supported.get(primary_role, set())


def collect_concept_confidence_calibration(
    archive_concepts: dict[str, Any] | None = None,
    repo_role_classification: dict[str, Any] | None = None,
    *,
    source_path: str | None = None,
    metadata: dict[str, Any] | None = None,
    collect_concepts: ArchiveConceptCollector | None = None,
    validate_concepts: ArchiveConceptValidator | None = None,
    collect_repo_role: RepoRoleCollector | None = None,
    validate_repo_role: RepoRoleValidator | None = None,
) -> dict[str, Any]:
    if archive_concepts is None:
        if collect_concepts is None:
            raise ValueError("collect_concepts callback is required when archive_concepts is not supplied")
        concepts = collect_concepts(source_path=source_path)
    else:
        concepts = archive_concepts
    if validate_concepts is not None:
        validate_concepts(concepts)
    if repo_role_classification is None:
        if collect_repo_role is None:
            raise ValueError("collect_repo_role callback is required when repo_role_classification is not supplied")
        role = collect_repo_role(concepts)
    else:
        role = repo_role_classification
    if validate_repo_role is not None:
        validate_repo_role(role, concepts)
    primary_role = role["primary_role"]
    calibrations: list[dict[str, Any]] = []
    overconfident: list[dict[str, Any]] = []
    downranked: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    for concept in concepts["detected_concepts"]:
        original = int(concept["confidence"])
        calibrated = original
        reasons: list[str] = []
        status = "unchanged"
        family = concept["concept_family"]
        if family in {"compression", "rag"} and primary_role != "compression_context":
            calibrated = min(calibrated, 34 if primary_role in {"crawler_source_collection", "business_reach_outreach", "ai_workflow_builder", "workflow_automation"} else 52)
            reasons.append(f"downranked because primary repo role is {primary_role}, not compression_context")
        elif role_supports_concept(primary_role, family):
            calibrated = min(95, calibrated + 8)
            reasons.append(f"kept/promoted because concept family aligns with {primary_role}")
        if len(concept.get("source_refs", [])) <= 1 or len(concept.get("evidence_refs", [])) <= 1:
            calibrated = min(calibrated, original - 8 if original >= 45 else original)
            reasons.append("thin evidence refs limited confidence")
        calibrated = max(0, min(100, calibrated))
        adjustment = calibrated - original
        if calibrated < 35:
            status = "rejected"
        elif adjustment < 0:
            status = "downranked"
        elif adjustment > 0:
            status = "promoted"
        entry = {
            "concept_id": concept["concept_id"],
            "concept_name": concept["concept_name"],
            "concept_family": family,
            "original_confidence": original,
            "calibrated_confidence": calibrated,
            "confidence_label": concept_confidence_label(calibrated),
            "adjustment": adjustment,
            "adjustment_reasons": reasons or ["no calibration adjustment"],
            "positive_evidence_refs": concept["evidence_refs"][:4] if adjustment >= 0 else [],
            "negative_evidence_refs": concept["evidence_refs"][:4] if adjustment < 0 else [],
            "source_refs": concept["source_refs"][:4],
            "status": status,
        }
        calibrations.append(entry)
        if original >= 75 and calibrated < 55:
            overconfident.append(entry)
        if status in {"downranked", "rejected"}:
            downranked.append(entry)
        if status == "promoted":
            promoted.append(entry)
    expected_family_by_role = {
        "compression_context": "compression",
        "crawler_source_collection": "crawler",
        "business_reach_outreach": "business_growth",
        "workflow_automation": "workflow_automation",
        "ai_workflow_builder": "workflow_automation",
        "agent_memory_retrieval": "agent_memory",
    }
    expected_family = expected_family_by_role.get(primary_role)
    missing_expected = []
    if expected_family and not any(item["concept_family"] == expected_family and item["calibrated_confidence"] >= 35 for item in calibrations):
        missing_expected.append({
            "expected_concept_family": expected_family,
            "reason": f"primary role {primary_role} lacks medium calibrated concept support",
        })
    payload = {
        "concept_confidence_calibration_version": CONCEPT_CONFIDENCE_CALIBRATION_VERSION,
        "concept_confidence_calibration_id": "concept-confidence-calibration-" + _hash_text({"concepts_id": concepts["source_aware_archive_concepts_id"], "role_id": role["calibrated_repo_role_classification_id"], "version": CONCEPT_CONFIDENCE_CALIBRATION_VERSION})[:12],
        "source_path": concepts["source_path"],
        "archive_concepts_id": concepts["source_aware_archive_concepts_id"],
        "repo_role_classification_id": role["calibrated_repo_role_classification_id"],
        "concept_calibrations": calibrations,
        "overconfident_concepts": overconfident,
        "downranked_concepts": downranked,
        "promoted_concepts": promoted,
        "missing_expected_concepts": missing_expected,
        "recommended_next_action": "Use calibrated concept confidence for profile and opportunity scoring.",
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_concept_confidence_calibration(payload, concepts, role)
    return payload


def validate_concept_confidence_calibration(payload: dict[str, Any], archive_concepts: dict[str, Any] | None = None, repo_role_classification: dict[str, Any] | None = None) -> None:
    required = ("concept_confidence_calibration_version", "concept_confidence_calibration_id", "source_path", "archive_concepts_id", "repo_role_classification_id", "concept_calibrations", "overconfident_concepts", "downranked_concepts", "promoted_concepts", "missing_expected_concepts", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"concept confidence calibration missing field: {key}")
    if payload["concept_confidence_calibration_version"] != CONCEPT_CONFIDENCE_CALIBRATION_VERSION:
        raise ValueError("invalid concept confidence calibration version")
    if not isinstance(payload["concept_calibrations"], list):
        raise TypeError("concept confidence calibrations must be a list")
    for item in payload["concept_calibrations"]:
        for key in ("concept_id", "concept_name", "concept_family", "original_confidence", "calibrated_confidence", "confidence_label", "adjustment", "adjustment_reasons", "positive_evidence_refs", "negative_evidence_refs", "source_refs", "status"):
            if key not in item:
                raise ValueError(f"concept calibration missing field: {key}")
        if not 0 <= int(item["calibrated_confidence"]) <= 100:
            raise ValueError("calibrated concept confidence must be 0..100")
        if item["status"] not in {"promoted", "unchanged", "downranked", "rejected", "needs_more_evidence"}:
            raise ValueError("invalid concept calibration status")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("concept confidence calibration must be deterministic/no-model/no-network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("concept confidence calibration must remain read-only")
    if archive_concepts is not None and payload["archive_concepts_id"] != archive_concepts["source_aware_archive_concepts_id"]:
        raise ValueError("concept confidence archive concepts id mismatch")
    if repo_role_classification is not None and payload["repo_role_classification_id"] != repo_role_classification["calibrated_repo_role_classification_id"]:
        raise ValueError("concept confidence role id mismatch")


def stable_concept_confidence_calibration_json(payload: dict[str, Any]) -> str:
    validate_concept_confidence_calibration(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_concept_confidence_calibration_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_concept_confidence_calibration(payload)
    return payload
