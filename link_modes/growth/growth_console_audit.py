#!/usr/bin/env python3
"""Static Growth console monolith audit.

This module intentionally does not import link_growth_console.py. It reads the
file as text, parses its AST, and produces a deterministic modularization map.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


AUDIT_VERSION = "growth-console-audit-v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_FILE = ROOT / "link_modes/growth/link_growth_console.py"
DEFAULT_REFERENCE_FILES = (
    ROOT / "link.py",
    ROOT / "tests/test_growth_pipeline.py",
    ROOT / "link_healthcheck.py",
)
_AUDIT_CACHE: dict[tuple[str, int, int, int, str], dict[str, Any]] = {}
MODULE_BOUNDARY_RULES = (
    {
        "proposed_module": "growth_source_queue.py",
        "description": "Default source queue policy, suitability, quarantine, status, and warmup orchestration.",
        "symbol_prefixes": ("collect_growth_source_queue", "growth_source_queue", "collect_source_queue", "source_queue"),
        "keywords": ("source_queue", "source-queue", "quarantine", "suitability"),
        "recommended_order": 6,
        "extraction_risk": "high",
    },
    {
        "proposed_module": "growth_source_cache.py",
        "description": "Persistent source inventory cache keys, manifests, status, observability, and clear/warm helpers.",
        "symbol_prefixes": ("collect_source_archive_intake_cache", "growth_source_cache", "persistent_source", "source_cache"),
        "keywords": ("source_cache", "persistent_cache", "source_inventory", "cache_manifest"),
        "recommended_order": 6,
        "extraction_risk": "high",
    },
    {
        "proposed_module": "growth_queue_e2e_cache.py",
        "description": "Compact queue E2E summary cache key, status, read, write, and fast-mode reuse helpers.",
        "symbol_prefixes": ("collect_growth_source_queue_e2e", "growth_source_queue_e2e", "summarize_queue_e2e"),
        "keywords": ("queue_e2e", "e2e_cache", "compact_cache"),
        "recommended_order": 5,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_direct_upgrade_eval.py",
        "description": "Direct upgrade evaluator, per-target reuse summaries, cache plan, and human/JSON surfaces.",
        "symbol_prefixes": ("collect_growth_direct", "growth_direct_upgrade", "_growth_direct"),
        "keywords": ("direct_upgrade", "direct_eval", "per_target_summary"),
        "recommended_order": 4,
        "extraction_risk": "high",
    },
    {
        "proposed_module": "growth_operator_cache_dashboard.py",
        "description": "Read-only operator cache dashboard, readiness checks, cache layer summaries, and next actions.",
        "symbol_prefixes": ("collect_growth_operator_cache", "growth_operator_cache", "_growth_operator_cache"),
        "keywords": ("operator_cache_dashboard", "cache_dashboard"),
        "recommended_order": 3,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_operator_qa.py",
        "description": "Deterministic operator QA check, issue inventory, ROI candidates, and human summary.",
        "symbol_prefixes": ("collect_growth_operator_qa", "growth_operator_qa", "_growth_operator_qa"),
        "keywords": ("operator_qa", "qa_check", "candidate_roi"),
        "recommended_order": 3,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_repo_role_calibration.py",
        "description": "Repository role classification, role confidence, and calibrated role evidence.",
        "symbol_prefixes": ("collect_calibrated_repo_role", "research_repo_role", "repo_role"),
        "keywords": ("repo_role", "role_classification", "calibrated_repo"),
        "recommended_order": 7,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_concept_confidence.py",
        "description": "Concept extraction, concept confidence calibration, and concept calibration reports.",
        "symbol_prefixes": ("collect_concept", "collect_repo_concept", "research_concept", "growth_concept"),
        "keywords": ("concept_confidence", "concept_calibration", "archive_concepts"),
        "recommended_order": 7,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_task_draft_alignment.py",
        "description": "Task draft construction, source-aware task alignment, and operator task handoff helpers.",
        "symbol_prefixes": ("collect_research_target_operator_task", "operator_task", "research_target_task"),
        "keywords": ("task_draft", "task_alignment", "operator_task"),
        "recommended_order": 8,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_human_renderers.py",
        "description": "Pure human output renderers and compact terminal summaries.",
        "symbol_prefixes": ("render_", "_render_"),
        "keywords": ("render_", "human"),
        "recommended_order": 2,
        "extraction_risk": "low",
    },
    {
        "proposed_module": "growth_schema_helpers.py",
        "description": "Stable JSON, parse, validate, normalization, and schema compatibility helpers.",
        "symbol_prefixes": ("stable_", "parse_", "validate_", "_normalize", "_stable"),
        "keywords": ("stable_", "parse_", "validate_", "schema"),
        "recommended_order": 2,
        "extraction_risk": "medium",
    },
    {
        "proposed_module": "growth_legacy_compat.py",
        "description": "Older proposal/archive/advisor/business compatibility surfaces that should be moved last.",
        "symbol_prefixes": ("archive_", "business_", "advisor_", "control_plane_", "governance_", "simulation_"),
        "keywords": ("legacy", "archive_", "advisor_", "business_", "governance", "simulation"),
        "recommended_order": 9,
        "extraction_risk": "high",
    },
)


def _stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"


def _hash_payload(data: Any) -> str:
    return hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()[:12]


def _line_count(text: str) -> int:
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _node_line_count(node: ast.AST) -> int:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", start) or start)
    return max(1, end - start + 1)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _safe_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _reference_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = _read_text(path)
    names: set[str] = set()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "link_modes.growth.link_growth_console":
            for alias in node.names:
                names.add(alias.name)
    return names


def _all_word_references(path: Path, symbols: set[str]) -> set[str]:
    if not path.exists() or not symbols:
        return set()
    found: set[str] = set()
    try:
        tree = ast.parse(_read_text(path), filename=str(path))
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in symbols:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in symbols:
            found.add(node.attr)
        elif isinstance(node, ast.ImportFrom) and node.module == "link_modes.growth.link_growth_console":
            for alias in node.names:
                if alias.name in symbols:
                    found.add(alias.name)
    return found


def _called_names(node: ast.AST) -> set[str]:
    called: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    return called


def _category_guess(name: str) -> str:
    lowered = name.lower()
    if name.endswith("_main") or lowered == "main":
        return "CLI_entrypoint"
    if name.startswith(("stable_",)):
        return "schema_helper"
    if name.startswith(("parse_", "validate_")):
        return "parser_validator_helper"
    if name.startswith(("render_", "_render_")):
        return "human_renderer"
    if "operator_qa" in lowered:
        return "hot_operator_path_candidate"
    if "operator_cache" in lowered or "direct_upgrade" in lowered:
        return "hot_operator_path_candidate"
    if "source_queue" in lowered or "source_cache" in lowered or "queue_e2e" in lowered:
        return "cache_layer_candidate"
    if "repo_role" in lowered or "concept_confidence" in lowered or "concept_calibration" in lowered:
        return "calibration_candidate"
    if any(token in lowered for token in ("archive", "proposal", "approve", "reject", "handoff", "advisor", "business", "governance")):
        return "legacy_compatibility_candidate"
    return "unknown_needs_review"


def _symbol_matches_rule(name: str, rule: dict[str, Any]) -> bool:
    lowered = name.lower()
    prefixes = tuple(rule.get("symbol_prefixes", ()))
    if prefixes and name.startswith(prefixes):
        return True
    return any(str(keyword).lower() in lowered for keyword in rule.get("keywords", ()))


def _collect_module_boundaries(functions: list[dict[str, Any]], call_map: dict[str, set[str]]) -> list[dict[str, Any]]:
    by_name = {item["name"]: item for item in functions}
    boundaries: list[dict[str, Any]] = []
    for rule in MODULE_BOUNDARY_RULES:
        symbols = [item["name"] for item in functions if _symbol_matches_rule(item["name"], rule)]
        line_count = sum(by_name[name]["line_count"] for name in symbols)
        external_calls: set[str] = set()
        symbol_set = set(symbols)
        for name in symbols:
            external_calls.update(called for called in call_map.get(name, set()) if called in by_name and called not in symbol_set)
        dependency_categories = sorted({_category_guess(name) for name in external_calls if _category_guess(name) != "unknown_needs_review"})
        boundaries.append({
            "proposed_module": rule["proposed_module"],
            "description": rule["description"],
            "symbol_prefixes": list(rule["symbol_prefixes"]),
            "candidate_symbols": symbols,
            "approximate_line_count": line_count,
            "extraction_risk": rule["extraction_risk"],
            "dependencies": dependency_categories[:12],
            "recommended_order": rule["recommended_order"],
            "rationale": "Static name/prefix clustering. Extract behind compatibility wrappers; do not delete old entrypoints.",
        })
    return boundaries


def collect_growth_console_audit(
    *,
    source_file: str | Path | None = None,
    top: int = 25,
    category: str = "all",
) -> dict[str, Any]:
    source_path = Path(source_file) if source_file else DEFAULT_SOURCE_FILE
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    stat = source_path.stat()
    cache_key = (str(source_path.resolve()), int(stat.st_mtime_ns), int(stat.st_size), int(top), str(category))
    if cache_key in _AUDIT_CACHE:
        return _AUDIT_CACHE[cache_key]
    text = _read_text(source_path)
    tree = ast.parse(text, filename=str(source_path))
    top = max(1, min(int(top), 100))
    category = category if category in {"hot", "legacy", "schema", "cache", "operator", "all"} else "all"

    functions: list[dict[str, Any]] = []
    call_map: dict[str, set[str]] = {}
    classes = 0
    imports = 0
    top_level_assignments = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            line_count = _node_line_count(node)
            category_guess = _category_guess(name)
            functions.append({
                "name": name,
                "start_line": int(node.lineno),
                "end_line": int(getattr(node, "end_lineno", node.lineno)),
                "line_count": line_count,
                "category_guess": category_guess,
                "extraction_risk": "high" if line_count >= 120 or category_guess == "CLI_entrypoint" else "medium" if line_count >= 50 else "low",
                "notes": [],
            })
            call_map[name] = _called_names(node)
        elif isinstance(node, ast.ClassDef):
            classes += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports += 1
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            top_level_assignments += 1

    function_names = {item["name"] for item in functions}
    intra_called = {name for calls in call_map.values() for name in calls if name in function_names}
    link_refs = _reference_names(ROOT / "link.py") | _all_word_references(ROOT / "link.py", function_names)
    test_refs = _reference_names(ROOT / "tests/test_growth_pipeline.py") | _all_word_references(ROOT / "tests/test_growth_pipeline.py", function_names)
    health_refs = _reference_names(ROOT / "link_healthcheck.py") | _all_word_references(ROOT / "link_healthcheck.py", function_names)
    externally_referenced = link_refs | test_refs | health_refs

    for item in functions:
        notes = item["notes"]
        name = item["name"]
        if name in link_refs:
            notes.append("referenced_by_link_py")
        if name in test_refs:
            notes.append("referenced_by_tests")
        if name in health_refs:
            notes.append("referenced_by_healthcheck")
        if name in intra_called:
            notes.append("called_within_monolith")
        if name not in intra_called and name not in externally_referenced:
            notes.append("no_static_reference_found")

    largest = sorted(functions, key=lambda item: (-item["line_count"], item["start_line"]))[:top]
    cli_entrypoints = sorted(item["name"] for item in functions if item["name"].endswith("_main") or item["name"] == "main")
    schema_helpers = sorted(item["name"] for item in functions if _category_guess(item["name"]) in {"schema_helper", "parser_validator_helper"})
    hot_operator = sorted(
        item["name"] for item in functions
        if _category_guess(item["name"]) == "hot_operator_path_candidate" or any(token in item["name"] for token in ("source_queue_e2e", "source_cache", "concept_calibration"))
    )
    legacy = sorted(item["name"] for item in functions if _category_guess(item["name"]) == "legacy_compatibility_candidate")
    unreferenced = sorted(
        (item for item in functions if "no_static_reference_found" in item["notes"]),
        key=lambda item: (item["category_guess"], item["name"]),
    )
    module_boundaries = _collect_module_boundaries(functions, call_map)

    symbol_categories = {
        "CLI_entrypoint": cli_entrypoints,
        "test_referenced": sorted(test_refs & function_names),
        "link_py_referenced": sorted(link_refs & function_names),
        "healthcheck_referenced": sorted(health_refs & function_names),
        "internal_referenced": sorted(intra_called),
        "schema_helper": [name for name in schema_helpers if name.startswith("stable_")],
        "parser_validator_helper": [name for name in schema_helpers if name.startswith(("parse_", "validate_"))],
        "human_renderer": sorted(item["name"] for item in functions if _category_guess(item["name"]) == "human_renderer"),
        "hot_operator_path_candidate": hot_operator,
        "cache_layer_candidate": sorted(item["name"] for item in functions if _category_guess(item["name"]) == "cache_layer_candidate"),
        "calibration_candidate": sorted(item["name"] for item in functions if _category_guess(item["name"]) == "calibration_candidate"),
        "legacy_compatibility_candidate": legacy,
        "unreferenced_candidate": [item["name"] for item in unreferenced],
        "unknown_needs_review": sorted(item["name"] for item in functions if _category_guess(item["name"]) == "unknown_needs_review"),
    }
    if category != "all":
        category_map = {
            "hot": {"hot_operator_path_candidate"},
            "legacy": {"legacy_compatibility_candidate"},
            "schema": {"schema_helper", "parser_validator_helper"},
            "cache": {"cache_layer_candidate"},
            "operator": {"hot_operator_path_candidate"},
        }
        allowed = category_map[category]
        largest = [item for item in sorted(functions, key=lambda item: (-item["line_count"], item["start_line"])) if item["category_guess"] in allowed][:top]

    unresolved_calls = sorted({called for calls in call_map.values() for called in calls if called not in function_names})
    extraction_candidates = [
        {
            "symbol": item["name"],
            "category_guess": item["category_guess"],
            "line_count": item["line_count"],
            "reason": "No static intra-file/link.py/test/healthcheck reference was found. Review manually before moving or deleting.",
            "recommended_action": "review_for_extraction_wrapper",
        }
        for item in unreferenced[:200]
    ]
    risk_notes = [
        "Static audit cannot prove runtime liveness for dynamic lookups, CLI compatibility, or external imports.",
        "Deletion candidates are intentionally empty; no function should be removed without explicit deprecation proof.",
        "Extract one subsystem at a time behind compatibility wrappers and keep stable JSON helpers available.",
    ]
    payload = {
        "growth_console_audit_id": "growth-console-audit-" + _hash_payload({
            "file": _safe_relative(source_path),
            "bytes": len(text.encode("utf-8")),
            "lines": _line_count(text),
            "functions": len(functions),
            "version": AUDIT_VERSION,
        }),
        "audit_version": AUDIT_VERSION,
        "source_file": _safe_relative(source_path),
        "source_file_bytes": len(text.encode("utf-8")),
        "source_file_lines": _line_count(text),
        "function_count": len(functions),
        "class_count": classes,
        "import_count": imports,
        "top_level_assignment_count": top_level_assignments,
        "largest_functions": largest,
        "symbol_categories": symbol_categories,
        "module_boundary_candidates": module_boundaries,
        "extraction_candidates": extraction_candidates,
        "deletion_candidates": [],
        "unresolved_symbols": unresolved_calls[:200],
        "cli_entrypoints": cli_entrypoints,
        "test_referenced_symbols": sorted(test_refs & function_names),
        "link_py_referenced_symbols": sorted(link_refs & function_names),
        "healthcheck_referenced_symbols": sorted(health_refs & function_names),
        "hot_operator_path_symbols": hot_operator,
        "legacy_compatibility_symbols": legacy,
        "schema_helper_symbols": schema_helpers,
        "risk_notes": risk_notes,
        "recommended_next_action": "Extract one low-risk pure renderer or schema helper cluster behind compatibility wrappers, then run fast Growth suites.",
        "fallback_allowed": False,
        "model_used": False,
        "external_network_used": False,
        "safety_metadata": {
            "read_only": True,
            "imports_monolith": False,
            "model_calls_allowed": False,
            "external_network_allowed": False,
            "source_mutation_allowed": False,
        },
    }
    validate_growth_console_audit(payload)
    _AUDIT_CACHE[cache_key] = payload
    return payload


def validate_growth_console_audit(payload: dict[str, Any]) -> None:
    required = (
        "growth_console_audit_id", "audit_version", "source_file", "source_file_bytes",
        "source_file_lines", "function_count", "class_count", "import_count",
        "top_level_assignment_count", "largest_functions", "symbol_categories",
        "module_boundary_candidates", "extraction_candidates", "deletion_candidates",
        "unresolved_symbols", "cli_entrypoints", "test_referenced_symbols",
        "link_py_referenced_symbols", "healthcheck_referenced_symbols",
        "hot_operator_path_symbols", "legacy_compatibility_symbols", "schema_helper_symbols",
        "risk_notes", "recommended_next_action", "fallback_allowed", "model_used",
        "external_network_used", "safety_metadata",
    )
    for key in required:
        if key not in payload:
            raise ValueError(f"growth console audit missing {key}")
    if payload["audit_version"] != AUDIT_VERSION:
        raise ValueError("invalid growth console audit version")
    if not str(payload["growth_console_audit_id"]).startswith("growth-console-audit-"):
        raise ValueError("invalid growth console audit id")
    if payload["source_file_bytes"] <= 0 or payload["source_file_lines"] <= 0 or payload["function_count"] <= 0:
        raise ValueError("growth console audit source metrics must be positive")
    if not payload["largest_functions"]:
        raise ValueError("growth console audit must include largest functions")
    for item in payload["largest_functions"]:
        for key in ("name", "start_line", "end_line", "line_count", "category_guess", "extraction_risk", "notes"):
            if key not in item:
                raise ValueError(f"largest function missing {key}")
    if not payload["module_boundary_candidates"]:
        raise ValueError("growth console audit must include module boundary candidates")
    for item in payload["module_boundary_candidates"]:
        for key in ("proposed_module", "description", "symbol_prefixes", "candidate_symbols", "approximate_line_count", "extraction_risk", "dependencies", "recommended_order", "rationale"):
            if key not in item:
                raise ValueError(f"module boundary candidate missing {key}")
    if not isinstance(payload["symbol_categories"], dict):
        raise TypeError("symbol_categories must be a dict")
    if payload["deletion_candidates"] != []:
        raise ValueError("growth console audit must not recommend deletion candidates")
    if payload["fallback_allowed"] is not False or payload["model_used"] is not False or payload["external_network_used"] is not False:
        raise ValueError("growth console audit must avoid model/network/fallback")
    safety = payload["safety_metadata"]
    if safety.get("imports_monolith") is not False or safety.get("read_only") is not True:
        raise ValueError("growth console audit must be static and read-only")


def stable_growth_console_audit_json(payload: dict[str, Any]) -> str:
    validate_growth_console_audit(payload)
    return _stable_json(payload)


def parse_growth_console_audit_json(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    validate_growth_console_audit(payload)
    return payload


def render_growth_console_audit_text(payload: dict[str, Any], *, top: int = 10) -> str:
    validate_growth_console_audit(payload)
    top = max(1, min(int(top), 25))
    lines = [
        "Growth Console Audit",
        "  file:",
        f"    path: {payload['source_file']}",
        f"    lines: {payload['source_file_lines']}",
        f"    bytes: {payload['source_file_bytes']}",
        f"    functions: {payload['function_count']}",
        f"    classes: {payload['class_count']}",
        f"    imports: {payload['import_count']}",
        "  largest functions:",
    ]
    for item in payload["largest_functions"][:top]:
        lines.append(f"    - {item['name']}: {item['line_count']} lines ({item['category_guess']}, risk {item['extraction_risk']})")
    categories = payload["symbol_categories"]
    lines.extend([
        "  hot operator path:",
        f"    symbols: {len(payload['hot_operator_path_symbols'])}",
        f"    cache-layer symbols: {len(categories.get('cache_layer_candidate', []))}",
        f"    schema helpers: {len(payload['schema_helper_symbols'])}",
        f"    legacy compatibility symbols: {len(payload['legacy_compatibility_symbols'])}",
        f"    unreferenced candidates: {len(categories.get('unreferenced_candidate', []))}",
        "  module boundaries:",
    ])
    for item in sorted(payload["module_boundary_candidates"], key=lambda entry: entry["recommended_order"]):
        lines.append(f"    - {item['proposed_module']}: {len(item['candidate_symbols'])} symbols, ~{item['approximate_line_count']} lines, risk {item['extraction_risk']}")
    lines.extend([
        "  extraction recommendation:",
        "    first safe extraction: pure human renderers or schema helper cluster behind compatibility wrappers",
        f"    next audit command: python3 link.py growth console-audit --json",
        "  safety:",
        "    model used: no",
        "    OpenRouter: no",
        "    network: no",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the Growth console monolith without importing it.")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    parser.add_argument("--top", type=int, default=25, help="number of largest functions to include")
    parser.add_argument("--category", choices=("hot", "legacy", "schema", "cache", "operator", "all"), default="all")
    parser.add_argument("--source-file", default=str(DEFAULT_SOURCE_FILE.relative_to(ROOT)), help="source file to audit")
    args = parser.parse_args(argv)
    payload = collect_growth_console_audit(source_file=args.source_file, top=args.top, category=args.category)
    if args.json:
        sys.stdout.write(stable_growth_console_audit_json(payload))
    else:
        sys.stdout.write(render_growth_console_audit_text(payload, top=min(args.top, 10)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
