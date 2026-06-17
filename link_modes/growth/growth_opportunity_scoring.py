"""Opportunity scoring subsystem for Growth.

Extracted from ``link_growth_console.py``.  This module owns the deterministic
Growth opportunity decision-score payload.  E2E summary collection, repo-role
classification, and concept confidence are supplied by callbacks.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION = "link-growth-opportunity-decision-score-v1"

SummaryCollector = Callable[..., dict[str, Any]]
SummaryValidator = Callable[[dict[str, Any]], None]
RoleCollector = Callable[..., dict[str, Any]]
ConceptConfidenceCollector = Callable[..., dict[str, Any]]
RoleSupportChecker = Callable[[str, str], bool]


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


def _normalize_refs(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        raise TypeError("implementation branch refs must be a string or list")
    normalized: list[str] = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError("implementation branch refs cannot contain empty strings")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid implementation branch ref: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def collect_growth_opportunity_decision_score(
    *,
    source_path: str,
    summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    collect_summary: SummaryCollector | None = None,
    validate_summary: SummaryValidator | None = None,
    collect_repo_role: RoleCollector,
    collect_concept_confidence: ConceptConfidenceCollector,
    role_supports_concept: RoleSupportChecker,
) -> dict[str, Any]:
    if summary is None:
        if collect_summary is None:
            raise ValueError("collect_summary callback is required when summary is not supplied")
        e2e = collect_summary(source_path=source_path)
    else:
        e2e = summary
    if validate_summary is not None:
        validate_summary(e2e)
    best = e2e["best_growth_opportunity"]
    role = collect_repo_role(source_path=e2e["source_path"])
    concept_confidence = collect_concept_confidence(source_path=e2e["source_path"], repo_role_classification=role)
    source_specificity = 9 if best["source_specific"] else 4
    evidence_support = 8 if best["evidence_refs"] and best["source_refs"] else 4
    feasibility = 8 if len(best["expected_files_to_touch"]) <= 4 else 6
    growth_value = 9 if best["concept_supported"] else 5
    safety_risk = min(10, max(1, int(best["safety_risk"]) // 10))
    operator_confidence = int(best["operator_confidence"])
    title_text = (best["title"] + " " + best.get("why_good", "") + " " + best.get("recommended_next_slice", "")).lower()
    compression_specific = any(term in title_text for term in ("compression", "compress", "token", "context reduction"))
    crawler_specific = any(term in title_text for term in ("crawler", "crawl", "source", "sitemap"))
    business_specific = any(term in title_text for term in ("reach", "outreach", "lead", "business", "growth"))
    role_alignment = 7
    calibration_warnings: list[str] = []
    rejected_due_to_role_mismatch: list[dict[str, Any]] = []
    false_positive_penalty = 0
    overclassification_penalty = 0
    primary_role = role["primary_role"]
    if compression_specific and primary_role != "compression_context":
        role_alignment = 3
        false_positive_penalty = 3
        overclassification_penalty = 2 if role["overclassification_warnings"] else 1
        calibration_warnings.append(f"compression-specific opportunity mismatches primary role {primary_role}")
        rejected_due_to_role_mismatch.append({"opportunity_id": best["opportunity_id"], "title": best["title"], "primary_role": primary_role, "reason": "compression opportunity requires compression_context primary role"})
    elif crawler_specific and primary_role == "crawler_source_collection":
        role_alignment = 9
        growth_value = max(growth_value, 8)
    elif business_specific and primary_role == "business_reach_outreach":
        role_alignment = 9
        growth_value = max(growth_value, 8)
    elif role_supports_concept(primary_role, e2e["top_concept_families"][0] if e2e["top_concept_families"] else "unknown"):
        role_alignment = 8
    concept_confidence_score = max([item["calibrated_confidence"] for item in concept_confidence["concept_calibrations"][:5]] or [0])
    concept_confidence_0_10 = max(1, min(10, concept_confidence_score // 10))
    direct_usefulness = max(0, min(10, int(round((source_specificity + evidence_support + feasibility + growth_value + role_alignment + concept_confidence_0_10 - safety_risk - false_positive_penalty - overclassification_penalty) / 5))))
    if false_positive_penalty:
        growth_value = max(3, growth_value - false_positive_penalty)
        operator_confidence = min(operator_confidence, 5)
    if source_specificity >= 7 and evidence_support >= 6 and feasibility >= 6 and growth_value >= 7 and safety_risk <= 5 and operator_confidence >= 7:
        decision = "accept"
        reason = "Opportunity is source-specific, evidence-backed, feasible, and bounded by read-only safety constraints."
    elif evidence_support < 6:
        decision = "needs_more_evidence"
        reason = "Evidence support is too weak for implementation planning."
    elif source_specificity < 7:
        decision = "too_generic"
        reason = "Opportunity is not specific enough to the selected source concepts."
    elif safety_risk > 5:
        decision = "blocked"
        reason = "Safety risk is too high for the next implementation slice."
    elif rejected_due_to_role_mismatch:
        decision = "needs_more_evidence"
        reason = "Opportunity is source-backed but mismatches the calibrated primary repo role."
    else:
        decision = "needs_more_evidence"
        reason = "Opportunity needs stronger operator confidence before implementation."
    payload = {
        "growth_opportunity_decision_score_version": GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION,
        "growth_opportunity_decision_score_id": "growth-opportunity-decision-score-" + _hash_text({"summary_id": e2e["source_aware_growth_e2e_summary_id"], "decision": decision, "version": GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION})[:12],
        "source_path": e2e["source_path"],
        "e2e_summary_id": e2e["source_aware_growth_e2e_summary_id"],
        "source_archive_intake_cache_id": e2e["source_archive_intake_cache_id"],
        "cache_key_id": e2e["cache_key_id"],
        "persistent_cache_policy_id": e2e.get("persistent_cache_policy_id", ""),
        "persistent_cache_manifest_id": e2e.get("persistent_cache_manifest_id", ""),
        "persistent_cache_record_id": e2e.get("persistent_cache_record_id", ""),
        "persistent_cache_hit": bool(e2e.get("persistent_cache_hit", False)),
        "persistent_cache_valid": bool(e2e.get("persistent_cache_valid", False)),
        "persistent_cache_write_performed": bool(e2e.get("persistent_cache_write_performed", False)),
        "cache_source": e2e.get("cache_source", "computed"),
        "invalidation_reasons": e2e.get("invalidation_reasons", []),
        "best_opportunity_id": best["opportunity_id"],
        "source_specificity_score": source_specificity,
        "evidence_support_score": evidence_support,
        "implementation_feasibility_score": feasibility,
        "link_growth_value_score": growth_value,
        "safety_risk_score": safety_risk,
        "operator_confidence_score": operator_confidence,
        "calibrated_repo_role_classification_id": role["calibrated_repo_role_classification_id"],
        "concept_confidence_calibration_id": concept_confidence["concept_confidence_calibration_id"],
        "role_alignment_score": role_alignment,
        "concept_confidence_score": concept_confidence_0_10,
        "false_positive_penalty": false_positive_penalty,
        "overclassification_penalty": overclassification_penalty,
        "calibrated_direct_usefulness_score": direct_usefulness,
        "calibration_warnings": _normalize_refs(calibration_warnings + role["overclassification_warnings"]),
        "rejected_due_to_role_mismatch": rejected_due_to_role_mismatch,
        "decision": decision,
        "reason": reason,
        "recommended_next_action": best["recommended_next_slice"],
        "fallback_allowed": False,
        "model_used": False,
        "safety_metadata": _read_only_safety_metadata(),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_growth_opportunity_decision_score(payload)
    return payload


def validate_growth_opportunity_decision_score(payload: dict[str, Any]) -> None:
    required = (
        "growth_opportunity_decision_score_version", "growth_opportunity_decision_score_id", "source_path",
        "e2e_summary_id", "source_archive_intake_cache_id", "cache_key_id",
        "persistent_cache_policy_id", "persistent_cache_manifest_id", "persistent_cache_record_id",
        "persistent_cache_hit", "persistent_cache_valid", "persistent_cache_write_performed",
        "cache_source", "invalidation_reasons",
        "best_opportunity_id", "source_specificity_score", "evidence_support_score",
        "implementation_feasibility_score", "link_growth_value_score", "safety_risk_score",
        "operator_confidence_score", "calibrated_repo_role_classification_id", "concept_confidence_calibration_id",
        "role_alignment_score", "concept_confidence_score", "false_positive_penalty", "overclassification_penalty",
        "calibrated_direct_usefulness_score", "calibration_warnings", "rejected_due_to_role_mismatch",
        "decision", "reason", "recommended_next_action", "fallback_allowed",
        "model_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes",
    )
    for key in required:
        if key not in payload:
            raise ValueError(f"growth opportunity decision score missing field: {key}")
    if payload["growth_opportunity_decision_score_version"] != GROWTH_OPPORTUNITY_DECISION_SCORE_VERSION:
        raise ValueError("invalid growth opportunity score version")
    if not payload["growth_opportunity_decision_score_id"].startswith("growth-opportunity-decision-score-"):
        raise ValueError("invalid growth opportunity score id")
    for field in ("source_specificity_score", "evidence_support_score", "implementation_feasibility_score", "link_growth_value_score", "safety_risk_score", "operator_confidence_score", "role_alignment_score", "concept_confidence_score", "false_positive_penalty", "overclassification_penalty", "calibrated_direct_usefulness_score"):
        if not isinstance(payload[field], int) or not 0 <= payload[field] <= 10:
            raise ValueError(f"{field} must be 0..10")
    if not isinstance(payload["calibration_warnings"], list) or not isinstance(payload["rejected_due_to_role_mismatch"], list):
        raise TypeError("calibration warnings and role mismatch rejections must be lists")
    if payload["decision"] not in {"accept", "needs_more_evidence", "too_generic", "blocked"}:
        raise ValueError("invalid growth opportunity decision")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False:
        raise ValueError("growth opportunity score must be deterministic and no-model")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("growth opportunity score must remain read-only")


def stable_growth_opportunity_decision_score_json(payload: dict[str, Any]) -> str:
    validate_growth_opportunity_decision_score(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_growth_opportunity_decision_score_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_opportunity_decision_score(payload)
    return payload
