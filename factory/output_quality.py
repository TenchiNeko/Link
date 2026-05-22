"""Output quality checks for factory role reports."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass
class QualityIssue:
    severity: str
    code: str
    message: str


_END_OK = tuple(".!?)]}`”’✅❌")


def assess_output_quality(text: str) -> list[dict]:
    issues: list[QualityIssue] = []
    stripped = (text or "").strip()

    if not stripped:
        return [asdict(QualityIssue("critical", "empty_output", "Output file is empty."))]

    if len(stripped) < 250:
        issues.append(QualityIssue("warning", "very_short", "Output is very short; check whether the role produced a real report."))

    if stripped.count("```") % 2:
        issues.append(QualityIssue("critical", "unclosed_code_fence", "Markdown code fence appears unclosed."))

    lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
    last = lines[-1] if lines else ""

    lower_last = last.lower().strip()
    unfinished_tail = (
        " and", " or", " the", " a", " an", " to", " for", " with", " by",
        " from", " of", " in", " on", " as", " that", " which", " including",
        ":", "-", "•"
    )

    if last and not last.endswith(_END_OK):
        issues.append(QualityIssue("warning", "suspicious_end", f"Output may end mid-thought: {last[:120]}"))

    if any(lower_last.endswith(tail) for tail in unfinished_tail):
        issues.append(QualityIssue("critical", "likely_truncated", f"Output appears truncated at the end: {last[:120]}"))

    for line in lines:
        if line.lstrip().startswith("|") and line.count("|") < 3:
            issues.append(QualityIssue("warning", "broken_table", "A markdown table row appears malformed."))
            break

    if re.search(r"\b(cut|reduce|increase|boost|improve)[^\n]{0,60}\b\d+\s*%", stripped, re.I):
        if not re.search(r"placeholder|source|citation|confirmed|must be verified|must be confirmed", stripped, re.I):
            issues.append(QualityIssue("warning", "unverified_metric_claim", "Output includes a percentage claim without an obvious source/placeholder warning."))

    required_gate_terms = ("approval", "internal", "not for external", "human")
    if not any(term in stripped.lower() for term in required_gate_terms):
        issues.append(QualityIssue("warning", "missing_approval_language", "Output may be missing internal-only / human-approval language."))

    return [asdict(issue) for issue in issues]


# === LU01 context/truncation hardening ===
def evaluate_context_integrity(manifest: dict) -> dict:
    """
    Surface context manifest integrity for QA summaries.

    Returns a compact quality result:
    {
      "status": "PASS"|"WARN"|"FAIL",
      "errors": [...],
      "warnings": [...]
    }
    """
    manifest = manifest or {}
    status = manifest.get("integrity_status", "FAIL")
    flags = list(manifest.get("blocking_flags", []) or [])
    warnings = list(manifest.get("manifest_warnings", []) or [])

    if not manifest:
        return {
            "status": "FAIL",
            "errors": ["no_context_manifest_provided"],
            "warnings": [],
        }

    if status == "FAIL" or flags:
        return {
            "status": "FAIL",
            "errors": flags or ["context_integrity_failure"],
            "warnings": warnings,
        }

    if status == "WARN":
        return {
            "status": "WARN",
            "errors": [],
            "warnings": warnings or ["non_blocking_truncation_detected"],
        }

    return {"status": "PASS", "errors": [], "warnings": warnings}

def context_manifest_quality_findings(manifest: dict) -> dict:
    """Alias used by healthcheck and final-gate code."""
    return evaluate_context_integrity(manifest)
# === end LU01 context/truncation hardening ===

