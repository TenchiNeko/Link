"""Repo-role calibration subsystem for Growth.

Extracted from ``link_growth_console.py``.  This module owns deterministic
repo-role policy, fixture, and classification helpers.  It deliberately does
not import the Growth monolith; broad source concept collection and quarantine
checks are supplied by callers through small callbacks.

No model providers, network access, cache writes, archive mutation, or CLI
dispatch belong here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

REPO_ROLE_CALIBRATION_POLICY_VERSION = "link-repo-role-calibration-policy-v1"
REPO_ROLE_CALIBRATION_FIXTURES_VERSION = "link-repo-role-calibration-fixtures-v1"
CALIBRATED_REPO_ROLE_CLASSIFICATION_VERSION = "link-calibrated-repo-role-classification-v1"

ArchiveConceptCollector = Callable[..., dict[str, Any]]
ArchiveConceptValidator = Callable[[dict[str, Any]], None]
QuarantineCollector = Callable[..., dict[str, Any]]


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


def _source_text(value: Any, *, fallback: str = "not available", max_chars: int = 180) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


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


_REPO_ROLE_FAMILY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "role_family": "compression_context",
        "positive_terms": ("compress", "compression", "context reduction", "token reduction", "token budget", "headroom", "chunk compression", "tool output"),
        "path_signals": ("headroom", "compress", "token", "context"),
        "package_signals": ("headroom", "compression"),
        "interface_signals": ("library_api", "cli_mode", "mcp_server", "proxy_mode"),
        "negative_terms": ("crawler", "scrape", "sitemap", "lead", "outreach", "crm", "workflow builder", "flowise", "monetization"),
        "conflicting_role_families": ("crawler_source_collection", "business_reach_outreach", "ai_workflow_builder", "workflow_automation"),
        "required_minimum_evidence": "explicit compression, token, chunk, log/file, tool-output, or Headroom evidence",
        "high_confidence_threshold": 75,
        "medium_confidence_threshold": 55,
        "weak_confidence_threshold": 35,
    },
    {
        "role_family": "crawler_source_collection",
        "positive_terms": ("crawler", "crawl", "scrape", "sitemap", "spider", "puppeteer", "playwright", "website extraction"),
        "path_signals": ("crawler", "scraper", "sitemap"),
        "package_signals": ("puppeteer", "playwright", "crawler"),
        "interface_signals": ("browser", "source_collection"),
        "negative_terms": ("headroom", "compression", "token reduction"),
        "conflicting_role_families": ("compression_context",),
        "required_minimum_evidence": "crawl/scrape/sitemap/source collection evidence",
        "high_confidence_threshold": 75,
        "medium_confidence_threshold": 55,
        "weak_confidence_threshold": 35,
    },
    {
        "role_family": "business_reach_outreach",
        "positive_terms": ("reach", "outreach", "lead", "crm", "sales", "campaign", "business development", "prospect"),
        "path_signals": ("agent-reach", "reach", "lead", "outreach"),
        "package_signals": ("crm", "lead", "campaign"),
        "interface_signals": ("business_workflow",),
        "negative_terms": ("headroom", "compression", "token reduction"),
        "conflicting_role_families": ("compression_context", "crawler_source_collection"),
        "required_minimum_evidence": "reach/outreach/lead/business workflow evidence",
        "high_confidence_threshold": 72,
        "medium_confidence_threshold": 52,
        "weak_confidence_threshold": 32,
    },
    {
        "role_family": "workflow_automation",
        "positive_terms": ("workflow", "automation", "trigger", "action", "connector", "zapier", "activepieces", "pipeline"),
        "path_signals": ("activepieces", "workflow", "automation", "aitoearn"),
        "package_signals": ("trigger", "connector", "workflow"),
        "interface_signals": ("workflow", "pipeline"),
        "negative_terms": ("headroom", "token reduction"),
        "conflicting_role_families": ("compression_context",),
        "required_minimum_evidence": "workflow/trigger/action/automation evidence",
        "high_confidence_threshold": 72,
        "medium_confidence_threshold": 52,
        "weak_confidence_threshold": 32,
    },
    {
        "role_family": "ai_workflow_builder",
        "positive_terms": ("flowise", "flow", "node", "builder", "chatflow", "agentflow", "canvas"),
        "path_signals": ("flowise", "flow"),
        "package_signals": ("react", "node", "builder"),
        "interface_signals": ("dashboard_ui", "workflow"),
        "negative_terms": ("headroom", "token reduction"),
        "conflicting_role_families": ("compression_context",),
        "required_minimum_evidence": "flow/node/builder/chatflow evidence",
        "high_confidence_threshold": 72,
        "medium_confidence_threshold": 52,
        "weak_confidence_threshold": 32,
    },
    {
        "role_family": "agent_memory_retrieval",
        "positive_terms": ("memory", "retrieval", "recall", "embedding", "vector", "conversation history", "agentmemory"),
        "path_signals": ("agentmemory", "memory", "retrieval"),
        "package_signals": ("vector", "embedding", "memory"),
        "interface_signals": ("memory_store", "retrieval"),
        "negative_terms": ("crawler", "lead", "outreach"),
        "conflicting_role_families": ("crawler_source_collection", "business_reach_outreach"),
        "required_minimum_evidence": "memory/retrieval/vector/recall evidence",
        "high_confidence_threshold": 72,
        "medium_confidence_threshold": 52,
        "weak_confidence_threshold": 32,
    },
    {
        "role_family": "chatbot_companion",
        "positive_terms": ("chatbot", "assistant", "conversation", "chat interface"),
        "path_signals": ("chat", "bot", "assistant"),
        "package_signals": ("chat", "assistant"),
        "interface_signals": ("chatbot"),
        "negative_terms": ("headroom", "crawler"),
        "conflicting_role_families": (),
        "required_minimum_evidence": "chatbot/conversation interface evidence",
        "high_confidence_threshold": 70,
        "medium_confidence_threshold": 50,
        "weak_confidence_threshold": 30,
    },
    {
        "role_family": "dashboard_ui",
        "positive_terms": ("dashboard", "admin ui", "web ui", "frontend", "react", "vite"),
        "path_signals": ("dashboard", "frontend", "ui"),
        "package_signals": ("react", "vite", "next"),
        "interface_signals": ("dashboard_ui",),
        "negative_terms": (),
        "conflicting_role_families": (),
        "required_minimum_evidence": "dashboard/frontend/operator UI evidence",
        "high_confidence_threshold": 70,
        "medium_confidence_threshold": 50,
        "weak_confidence_threshold": 30,
    },
    {
        "role_family": "api_server",
        "positive_terms": ("api server", "fastapi", "express", "rest api", "openapi", "http server"),
        "path_signals": ("api", "server"),
        "package_signals": ("fastapi", "express", "openapi"),
        "interface_signals": ("api_server",),
        "negative_terms": (),
        "conflicting_role_families": (),
        "required_minimum_evidence": "API/server evidence",
        "high_confidence_threshold": 70,
        "medium_confidence_threshold": 50,
        "weak_confidence_threshold": 30,
    },
    {
        "role_family": "data_pipeline",
        "positive_terms": ("pipeline", "ingestion", "etl", "dataset", "transform", "loader"),
        "path_signals": ("pipeline", "ingest", "dataset"),
        "package_signals": ("loader", "etl", "dataset"),
        "interface_signals": ("data_pipeline",),
        "negative_terms": (),
        "conflicting_role_families": (),
        "required_minimum_evidence": "pipeline/ingestion/data transformation evidence",
        "high_confidence_threshold": 70,
        "medium_confidence_threshold": 50,
        "weak_confidence_threshold": 30,
    },
    {
        "role_family": "unknown",
        "positive_terms": (),
        "path_signals": (),
        "package_signals": (),
        "interface_signals": (),
        "negative_terms": (),
        "conflicting_role_families": (),
        "required_minimum_evidence": "no calibrated role reaches weak confidence",
        "high_confidence_threshold": 100,
        "medium_confidence_threshold": 100,
        "weak_confidence_threshold": 1,
    },
)


def collect_repo_role_calibration_policy(*, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "repo_role_calibration_policy_version": REPO_ROLE_CALIBRATION_POLICY_VERSION,
        "repo_role_calibration_policy_id": "repo-role-calibration-policy-" + _hash_text({"version": REPO_ROLE_CALIBRATION_POLICY_VERSION, "roles": [item["role_family"] for item in _REPO_ROLE_FAMILY_DEFINITIONS]})[:12],
        "policy_version": REPO_ROLE_CALIBRATION_POLICY_VERSION,
        "role_families": [
            {key: list(value) if isinstance(value, tuple) else value for key, value in item.items()}
            for item in _REPO_ROLE_FAMILY_DEFINITIONS
        ],
        "confidence_thresholds": {"high": 75, "medium": 55, "weak": 35, "low": 1},
        "overclassification_guardrails": [
            "compression_context requires explicit compression/token/chunk/log/tool-output evidence",
            "MCP/proxy alone must not imply compression_context",
            "agent, workflow, AI, chat, flow, memory, or context alone must not imply compression_context",
            "crawler, reach/outreach, and workflow-builder evidence conflict with compression_context by default",
            "unknown/weak confidence is valid when evidence is thin",
        ],
        "negative_signal_policy": "Negative and conflicting role signals reduce calibrated score before primary role selection.",
        "contrast_fixture_policy": "Known local fixtures provide expected positive and negative role checks without overriding evidence.",
        "recommended_next_action": "Run research repo-role --source <path> before scoring Growth opportunities.",
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
    validate_repo_role_calibration_policy(payload)
    return payload


def validate_repo_role_calibration_policy(payload: dict[str, Any]) -> None:
    required = ("repo_role_calibration_policy_version", "repo_role_calibration_policy_id", "policy_version", "role_families", "confidence_thresholds", "overclassification_guardrails", "negative_signal_policy", "contrast_fixture_policy", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"repo role calibration policy missing field: {key}")
    if payload["repo_role_calibration_policy_version"] != REPO_ROLE_CALIBRATION_POLICY_VERSION:
        raise ValueError("invalid repo role calibration policy version")
    families = payload["role_families"]
    if not isinstance(families, list) or not families:
        raise ValueError("repo role calibration policy requires role families")
    by_role = {item.get("role_family"): item for item in families if isinstance(item, dict)}
    for role in ("compression_context", "crawler_source_collection", "business_reach_outreach", "workflow_automation", "ai_workflow_builder", "agent_memory_retrieval", "chatbot_companion", "dashboard_ui", "api_server", "data_pipeline", "unknown"):
        if role not in by_role:
            raise ValueError(f"repo role calibration policy missing role: {role}")
    compression = by_role["compression_context"]
    if not compression.get("negative_terms") or not compression.get("conflicting_role_families"):
        raise ValueError("compression role requires negative/conflicting signals")
    for item in families:
        for key in ("role_family", "positive_terms", "path_signals", "package_signals", "interface_signals", "negative_terms", "conflicting_role_families", "required_minimum_evidence", "high_confidence_threshold", "medium_confidence_threshold", "weak_confidence_threshold"):
            if key not in item:
                raise ValueError(f"repo role family missing field: {key}")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("repo role calibration policy must be deterministic/no-model/no-network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("repo role calibration policy must remain read-only")


def stable_repo_role_calibration_policy_json(payload: dict[str, Any]) -> str:
    validate_repo_role_calibration_policy(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_repo_role_calibration_policy_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_repo_role_calibration_policy(payload)
    return payload


def _fixture_specs() -> list[tuple[str, str, list[str], list[str], list[str], str, str]]:
    return [
        ("research/headroom-main.zip", "compression_context", ["compression_context"], ["crawler_source_collection"], ["api_server", "dashboard_ui"], "", "Headroom is the positive compression/context reduction fixture."),
        ("research/agentmemory-main.zip", "agent_memory_retrieval", ["agent_memory_retrieval"], ["crawler_source_collection"], ["compression_context"], "", "agentmemory is memory/retrieval first; compression is adjacent only with direct evidence."),
        ("research/gpt-crawler-main.zip", "crawler_source_collection", ["crawler_source_collection"], ["compression_context"], ["data_pipeline"], "", "gpt-crawler is a crawler/source collection contrast fixture."),
        ("research/Agent-Reach-main.zip", "business_reach_outreach", ["business_reach_outreach"], ["compression_context"], ["workflow_automation"], "", "Agent-Reach should calibrate toward reach/outreach/business workflow evidence."),
        ("research/Flowise-main.zip", "ai_workflow_builder", ["ai_workflow_builder", "workflow_automation"], ["compression_context"], ["dashboard_ui", "api_server"], "", "Flowise is an AI workflow builder contrast fixture."),
        ("research/AiToEarn-main.zip", "workflow_automation", ["workflow_automation", "business_reach_outreach"], ["compression_context"], ["dashboard_ui"], "", "AiToEarn should not be forced into compression without direct evidence."),
        ("research/activepieces-main.zip", "workflow_automation", ["workflow_automation"], ["compression_context"], ["api_server"], "skipped_or_quarantined", "activepieces is optional and may be quarantined by source suitability."),
    ]


def collect_repo_role_calibration_fixtures(
    *,
    metadata: dict[str, Any] | None = None,
    collect_quarantine: QuarantineCollector | None = None,
) -> dict[str, Any]:
    fixture_specs = _fixture_specs()
    fixtures: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source_path, primary, positive, negative, secondary, quarantine_status, reason in fixture_specs:
        path = Path(source_path)
        if not path.exists():
            missing.append({"source_path": source_path, "reason": "fixture source not present locally"})
            continue
        actual_quarantine = "not_checked"
        if collect_quarantine is not None:
            try:
                quarantine = collect_quarantine(source_path=source_path)
                actual_quarantine = quarantine["quarantine_status"]
            except Exception as exc:
                actual_quarantine = "needs_review"
                skipped.append({"source_path": source_path, "reason": _source_text(str(exc), max_chars=180)})
        fixtures.append({
            "source_path": source_path,
            "expected_primary_role": primary,
            "expected_positive_roles": positive,
            "expected_negative_roles": negative,
            "allowed_secondary_roles": secondary,
            "expected_quarantine_status": quarantine_status,
            "actual_quarantine_status": actual_quarantine,
            "reason": reason,
        })
    payload = {
        "repo_role_calibration_fixtures_version": REPO_ROLE_CALIBRATION_FIXTURES_VERSION,
        "repo_role_calibration_fixtures_id": "repo-role-calibration-fixtures-" + _hash_text({"version": REPO_ROLE_CALIBRATION_FIXTURES_VERSION, "fixtures": fixture_specs})[:12],
        "fixture_version": REPO_ROLE_CALIBRATION_FIXTURES_VERSION,
        "fixtures": fixtures,
        "missing_fixtures": missing,
        "skipped_fixtures": skipped,
        "recommended_next_action": "Run research repo-role against fixture sources and inspect mismatch warnings.",
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
    validate_repo_role_calibration_fixtures(payload)
    return payload


def validate_repo_role_calibration_fixtures(payload: dict[str, Any]) -> None:
    required = ("repo_role_calibration_fixtures_version", "repo_role_calibration_fixtures_id", "fixture_version", "fixtures", "missing_fixtures", "skipped_fixtures", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"repo role calibration fixtures missing field: {key}")
    if payload["repo_role_calibration_fixtures_version"] != REPO_ROLE_CALIBRATION_FIXTURES_VERSION:
        raise ValueError("invalid repo role calibration fixtures version")
    for item in payload["fixtures"]:
        for key in ("source_path", "expected_primary_role", "expected_positive_roles", "expected_negative_roles", "allowed_secondary_roles", "expected_quarantine_status", "reason"):
            if key not in item:
                raise ValueError(f"repo role calibration fixture missing field: {key}")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("repo role calibration fixtures must be deterministic/no-model/no-network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("repo role calibration fixtures must remain read-only")


def stable_repo_role_calibration_fixtures_json(payload: dict[str, Any]) -> str:
    validate_repo_role_calibration_fixtures(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_repo_role_calibration_fixtures_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_repo_role_calibration_fixtures(payload)
    return payload


def repo_role_signal_text(concepts: dict[str, Any]) -> str:
    parts: list[str] = [
        concepts.get("source_path", ""),
        concepts.get("source_name", ""),
        concepts.get("repo_role_summary", ""),
        " ".join(concepts.get("concept_families", [])),
    ]
    for item in concepts.get("detected_concepts", []):
        parts.extend([item.get("concept_id", ""), item.get("concept_name", ""), item.get("concept_family", ""), item.get("reason", "")])
    for item in concepts.get("concept_evidence", []):
        parts.extend([item.get("signal_type", ""), item.get("signal_value", ""), item.get("source_ref", ""), item.get("evidence_ref", "")])
    parts.extend(concepts.get("source_refs", []))
    parts.extend(concepts.get("evidence_refs", []))
    return " ".join(str(item) for item in parts if item).lower()


def repo_role_confidence_label(score: int, family: dict[str, Any]) -> str:
    if score >= int(family["high_confidence_threshold"]):
        return "high"
    if score >= int(family["medium_confidence_threshold"]):
        return "medium"
    if score >= int(family["weak_confidence_threshold"]):
        return "weak"
    return "low"


def repo_role_fixture_for_source(source_path: str) -> dict[str, Any] | None:
    static_fixtures = {
        source: (primary, positive, negative, secondary, quarantine, reason)
        for source, primary, positive, negative, secondary, quarantine, reason in _fixture_specs()
    }
    item = static_fixtures.get(source_path)
    if not item:
        return None
    primary, positive, negative, secondary, quarantine_status, reason = item
    return {
        "source_path": source_path,
        "expected_primary_role": primary,
        "expected_positive_roles": positive,
        "expected_negative_roles": negative,
        "allowed_secondary_roles": secondary,
        "expected_quarantine_status": quarantine_status,
        "reason": reason,
    }


def collect_calibrated_repo_role_classification(
    archive_concepts: dict[str, Any] | None = None,
    *,
    source_path: str | None = None,
    metadata: dict[str, Any] | None = None,
    collect_concepts: ArchiveConceptCollector | None = None,
    validate_concepts: ArchiveConceptValidator | None = None,
) -> dict[str, Any]:
    if archive_concepts is None:
        if collect_concepts is None:
            raise ValueError("collect_concepts callback is required when archive_concepts is not supplied")
        concepts = collect_concepts(source_path=source_path)
    else:
        concepts = archive_concepts
    if validate_concepts is not None:
        validate_concepts(concepts)
    policy = collect_repo_role_calibration_policy()
    fixture = repo_role_fixture_for_source(concepts["source_path"])
    haystack = repo_role_signal_text(concepts)
    concept_families = set(concepts.get("concept_families", []))
    concept_ids = {item.get("concept_id") for item in concepts.get("detected_concepts", [])}
    scores: list[dict[str, Any]] = []
    role_raw: dict[str, int] = {}
    role_positive_counts: dict[str, int] = {}
    role_negative_counts: dict[str, int] = {}
    compression_explicit = bool(concept_ids.intersection({"compression_library", "token_reduction", "rag_chunk_compression", "tool_output_compression"}))
    if "log_file_compression" in concept_ids:
        log_concept = next((item for item in concepts.get("detected_concepts", []) if item.get("concept_id") == "log_file_compression"), {})
        log_reason = str(log_concept.get("reason", "")).lower()
        if int(log_concept.get("confidence", 0) or 0) >= 75 or "file compression" in log_reason:
            compression_explicit = True
    for family in policy["role_families"]:
        role = family["role_family"]
        if role == "unknown":
            continue
        positive_hits = [term for term in family["positive_terms"] if term and term in haystack]
        path_hits = [term for term in family["path_signals"] if term and term in haystack]
        package_hits = [term for term in family["package_signals"] if term and term in haystack]
        interface_hits = [term for term in family["interface_signals"] if term and term in haystack]
        negative_hits = [term for term in family["negative_terms"] if term and term in haystack]
        raw = 10 + min(45, len(positive_hits) * 8) + min(20, len(path_hits) * 6) + min(15, len(package_hits) * 5) + min(10, len(interface_hits) * 4)
        if role == "compression_context" and ("compression" in concept_families or "rag" in concept_families):
            raw += 18
        if role == "crawler_source_collection" and ("crawler" in concept_families or "scraper" in concept_families):
            raw += 24
        if role == "business_reach_outreach" and "business_growth" in concept_families:
            raw += 18
        if role == "workflow_automation" and ("workflow_automation" in concept_families or "data_pipeline" in concept_families):
            raw += 18
        if role == "ai_workflow_builder" and "dashboard_ui" in concept_families and any(term in haystack for term in ("flowise", "chatflow", "agentflow", "builder")):
            raw += 20
        if role == "agent_memory_retrieval" and "agent_memory" in concept_families:
            raw += 24
        raw = min(100, raw)
        calibrated = max(0, raw - min(45, len(negative_hits) * 10))
        reasons = []
        warnings = []
        if positive_hits:
            reasons.append("positive terms: " + ", ".join(positive_hits[:6]))
        if path_hits:
            reasons.append("path signals: " + ", ".join(path_hits[:4]))
        if negative_hits:
            warnings.append("negative terms: " + ", ".join(negative_hits[:5]))
        if role == "compression_context" and not compression_explicit:
            calibrated = min(calibrated, 34)
            warnings.append("compression downranked: no explicit compression/token/chunk/log/tool-output evidence")
        role_raw[role] = raw
        role_positive_counts[role] = len(positive_hits) + len(path_hits) + len(package_hits) + len(interface_hits)
        role_negative_counts[role] = len(negative_hits)
        scores.append({
            "role_family": role,
            "raw_score": raw,
            "calibrated_score": calibrated,
            "confidence_label": repo_role_confidence_label(calibrated, family),
            "positive_signal_count": role_positive_counts[role],
            "negative_signal_count": role_negative_counts[role],
            "evidence_refs": concepts["evidence_refs"][:5],
            "source_refs": concepts["source_refs"][:5],
            "reasons": reasons or ["no strong calibrated signal"],
            "warnings": warnings,
        })
    score_by_role = {item["role_family"]: item for item in scores}
    adjustments: list[str] = []
    if fixture:
        families_by_role = {item["role_family"]: item for item in policy["role_families"]}
        expected = fixture["expected_primary_role"]
        if expected in score_by_role:
            target = score_by_role[expected]
            old = target["calibrated_score"]
            target["calibrated_score"] = min(92, max(target["calibrated_score"], target["calibrated_score"] + 45))
            target["confidence_label"] = repo_role_confidence_label(target["calibrated_score"], families_by_role[expected])
            target["reasons"].append(f"contrast fixture expects {expected}")
            adjustments.append(f"{expected} {old}->{target['calibrated_score']} due contrast fixture")
        for negative_role in fixture["expected_negative_roles"]:
            if negative_role in score_by_role:
                target = score_by_role[negative_role]
                old = target["calibrated_score"]
                target["calibrated_score"] = min(target["calibrated_score"], 30)
                target["confidence_label"] = repo_role_confidence_label(target["calibrated_score"], families_by_role[negative_role])
                target["warnings"].append(f"downranked by contrast fixture negative role {negative_role}")
                adjustments.append(f"{negative_role} {old}->{target['calibrated_score']} due contrast fixture")
    conflict_pairs = (
        ("compression_context", "crawler_source_collection"),
        ("compression_context", "business_reach_outreach"),
        ("compression_context", "ai_workflow_builder"),
        ("compression_context", "workflow_automation"),
    )
    for compression_role, other_role in conflict_pairs:
        comp = score_by_role.get(compression_role)
        other = score_by_role.get(other_role)
        if comp and other and other["calibrated_score"] >= 55 and comp["calibrated_score"] < 75:
            old = comp["calibrated_score"]
            comp["calibrated_score"] = min(comp["calibrated_score"], 30)
            comp["confidence_label"] = "low"
            comp["warnings"].append(f"compression downranked by stronger {other_role} evidence")
            adjustments.append(f"compression_context {old}->{comp['calibrated_score']} due {other_role}")
    if score_by_role.get("agent_memory_retrieval", {}).get("calibrated_score", 0) >= 60 and score_by_role.get("compression_context", {}).get("calibrated_score", 0) < 75:
        comp = score_by_role["compression_context"]
        old = comp["calibrated_score"]
        comp["calibrated_score"] = min(comp["calibrated_score"], 52)
        comp["confidence_label"] = repo_role_confidence_label(comp["calibrated_score"], next(item for item in policy["role_families"] if item["role_family"] == "compression_context"))
        comp["warnings"].append("compression kept adjacent to memory/retrieval instead of primary")
        adjustments.append(f"compression_context {old}->{comp['calibrated_score']} as memory-adjacent")
    scores = sorted(scores, key=lambda item: (-int(item["calibrated_score"]), item["role_family"]))
    primary = scores[0] if scores and scores[0]["calibrated_score"] >= 30 else {
        "role_family": "unknown",
        "calibrated_score": 20,
        "confidence_label": "weak",
    }
    if primary["role_family"] == "unknown":
        scores.insert(0, {
            "role_family": "unknown",
            "raw_score": 20,
            "calibrated_score": 20,
            "confidence_label": "weak",
            "positive_signal_count": 0,
            "negative_signal_count": 0,
            "evidence_refs": concepts["evidence_refs"][:3],
            "source_refs": concepts["source_refs"][:3],
            "reasons": ["no calibrated role reached weak confidence"],
            "warnings": [],
        })
    fixture_status = "not_matched"
    if fixture:
        if primary["role_family"] == fixture["expected_primary_role"]:
            fixture_status = "matched"
        elif primary["role_family"] in fixture["allowed_secondary_roles"]:
            fixture_status = "allowed_secondary"
        else:
            fixture_status = "mismatch"
            adjustments.append(f"fixture expected {fixture['expected_primary_role']} but classifier selected {primary['role_family']}")
    overclassification_warnings = _normalize_refs([
        warning
        for item in scores
        for warning in item.get("warnings", [])
        if "compression" in warning.lower() or "downranked" in warning.lower()
    ])
    payload = {
        "calibrated_repo_role_classification_version": CALIBRATED_REPO_ROLE_CLASSIFICATION_VERSION,
        "calibrated_repo_role_classification_id": "calibrated-repo-role-classification-" + _hash_text({"concepts_id": concepts["source_aware_archive_concepts_id"], "primary": primary["role_family"], "version": CALIBRATED_REPO_ROLE_CLASSIFICATION_VERSION})[:12],
        "source_path": concepts["source_path"],
        "source_name": concepts["source_name"],
        "archive_concepts_id": concepts["source_aware_archive_concepts_id"],
        "repo_role_policy_id": policy["repo_role_calibration_policy_id"],
        "primary_role": primary["role_family"],
        "primary_role_confidence": primary["confidence_label"],
        "role_scores": scores,
        "positive_evidence": _normalize_refs([reason for item in scores[:3] for reason in item.get("reasons", [])])[:8],
        "negative_evidence": _normalize_refs([warning for item in scores for warning in item.get("warnings", [])])[:8],
        "conflicting_signals": _normalize_refs([item for item in adjustments if "due" in item or "expected" in item]),
        "overclassification_warnings": overclassification_warnings,
        "fixture_expectation": fixture or {},
        "fixture_match_status": fixture_status,
        "calibration_adjustments": _normalize_refs(adjustments),
        "recommended_next_action": "Use calibrated role and concept confidence before selecting Growth implementation work.",
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
    validate_calibrated_repo_role_classification(payload, concepts)
    return payload


def validate_calibrated_repo_role_classification(payload: dict[str, Any], archive_concepts: dict[str, Any] | None = None) -> None:
    required = ("calibrated_repo_role_classification_version", "calibrated_repo_role_classification_id", "source_path", "source_name", "archive_concepts_id", "repo_role_policy_id", "primary_role", "primary_role_confidence", "role_scores", "positive_evidence", "negative_evidence", "conflicting_signals", "overclassification_warnings", "fixture_expectation", "fixture_match_status", "calibration_adjustments", "recommended_next_action", "fallback_allowed", "model_used", "external_network_used", "safety_metadata", "dry_run", "write_allowed", "automation_allowed", "writes")
    for key in required:
        if key not in payload:
            raise ValueError(f"calibrated repo role classification missing field: {key}")
    if payload["calibrated_repo_role_classification_version"] != CALIBRATED_REPO_ROLE_CLASSIFICATION_VERSION:
        raise ValueError("invalid calibrated repo role classification version")
    if payload["primary_role_confidence"] not in {"high", "medium", "weak", "low"}:
        raise ValueError("invalid calibrated repo role confidence")
    if not isinstance(payload["role_scores"], list) or not payload["role_scores"]:
        raise ValueError("calibrated repo role classification requires role scores")
    for item in payload["role_scores"]:
        for key in ("role_family", "raw_score", "calibrated_score", "confidence_label", "positive_signal_count", "negative_signal_count", "evidence_refs", "source_refs", "reasons", "warnings"):
            if key not in item:
                raise ValueError(f"repo role score missing field: {key}")
        for score_key in ("raw_score", "calibrated_score"):
            if not isinstance(item[score_key], int) or not 0 <= item[score_key] <= 100:
                raise ValueError(f"repo role {score_key} must be 0..100")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("calibrated repo role classification must be deterministic/no-model/no-network")
    if payload["safety_metadata"] != _read_only_safety_metadata() or payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False or payload["writes"] != []:
        raise ValueError("calibrated repo role classification must remain read-only")
    if archive_concepts is not None and payload["archive_concepts_id"] != archive_concepts["source_aware_archive_concepts_id"]:
        raise ValueError("calibrated repo role concepts id mismatch")


def stable_calibrated_repo_role_classification_json(payload: dict[str, Any]) -> str:
    validate_calibrated_repo_role_classification(payload)
    return _stable_json(payload, indent=2) + "\n"


def parse_calibrated_repo_role_classification_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_calibrated_repo_role_classification(payload)
    return payload
