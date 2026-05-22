#!/usr/bin/env python3
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parent

def read_all(run_dir: Path) -> str:
    chunks = []
    for p in sorted(run_dir.glob("*.md")):
        chunks.append(f"\n--- {p.name} ---\n")
        chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)

def has_hard_truncation(text: str) -> bool:
    markers = [
        "[context truncated",
        "[dashboard display truncated]",
        "output truncated",
        "truncated by loader",
    ]
    return any(m.lower() in text.lower() for m in markers)

def load_context_manifest(run_dir: Path) -> dict:
    """
    Load optional context manifest for a run.

    Supported locations:
    - <run>/context_manifest.json
    - <run>/context_manifest.jsonl first JSON object
    - <run>/manifest.json context_manifest key, if present
    """
    candidates = [
        run_dir / "context_manifest.json",
        run_dir / "context_manifest.jsonl",
        run_dir / "manifest.json",
    ]

    for p in candidates:
        if not p.exists():
            continue
        try:
            if p.suffix == ".jsonl":
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        obj = json.loads(line)
                        return obj.get("context_manifest", obj)
            obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if isinstance(obj, dict):
                return obj.get("context_manifest", obj if "integrity_status" in obj else {})
        except Exception as exc:
            return {
                "integrity_status": "FAIL",
                "blocking_flags": [f"context_manifest_unreadable::{p.name}::{exc.__class__.__name__}"],
            }
    return {}

def check_context_integrity(manifest: dict) -> dict:
    """
    Final-gate context integrity diagnosis.

    PASS: no integrity issue.
    WARN: non-blocking truncation only.
    FAIL: deliverable missing/truncated, required sentinel missing/truncated,
          or explicit blocking flags.
    """
    if not manifest:
        return {"diagnosis": "PASS", "status": "PASS", "reasons": []}

    status = manifest.get("integrity_status", "FAIL")
    blocking = list(manifest.get("blocking_flags", []) or [])

    if blocking or status == "FAIL":
        return {
            "diagnosis": "FAIL",
            "status": "FAIL",
            "reasons": blocking or ["context_integrity_failure"],
        }

    if status == "WARN":
        return {
            "diagnosis": "WARN",
            "status": "WARN",
            "reasons": list(manifest.get("manifest_warnings", []) or ["non_blocking_truncation_detected"]),
        }

    return {"diagnosis": "PASS", "status": "PASS", "reasons": []}

def audit_run(run_dir: Path, required_terms=None) -> dict:
    required_terms = required_terms or []
    text = read_all(run_dir)
    manifest = load_context_manifest(run_dir)
    integrity = check_context_integrity(manifest)

    errors = []
    warnings = []

    if integrity["diagnosis"] == "FAIL":
        errors.extend(integrity["reasons"])
    elif integrity["diagnosis"] == "WARN":
        warnings.extend(integrity["reasons"])

    for term in required_terms:
        if term and term not in text:
            errors.append(f"missing_required_term::{term}")

    # Old QA/commentary truncation is warning-only unless the manifest says it clipped deliverables.
    truncated_files = []
    for p in sorted(run_dir.glob("*.md")):
        body = p.read_text(encoding="utf-8", errors="replace")
        if has_hard_truncation(body):
            truncated_files.append(p.name)

    deliverable_truncation = [
        name for name in truncated_files
        if "production" in name.lower() or "deliverable" in name.lower()
    ]

    if deliverable_truncation and not manifest:
        errors.extend(f"hard_truncation_in_deliverable::{name}" for name in deliverable_truncation)
    elif truncated_files:
        warnings.extend(f"non_blocking_truncation_marker::{name}" for name in truncated_files)

    verdict = "PASS" if not errors else "FAIL"
    return {
        "run_dir": str(run_dir),
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "context_integrity": integrity,
    }

def render_report(results: list[dict]) -> str:
    overall = "APPROVE DRAFT" if all(r["verdict"] == "PASS" for r in results) else "REVISE"
    lines = [
        "# Final Gate Terminal Audit",
        "",
        "Deterministic local audit with context-manifest integrity support.",
        "",
        "## Verdict",
        "",
        f"**{overall}**",
        "",
        "## Run Results",
        "",
        "| Run | Result | Errors | Warnings |",
        "|---|---|---|---|",
    ]

    for r in results:
        lines.append(
            f"| `{r['run_dir']}` | **{r['verdict']}** | "
            f"{'; '.join(r['errors']) if r['errors'] else 'None'} | "
            f"{'; '.join(r['warnings']) if r['warnings'] else 'None'} |"
        )

    return "\n".join(lines) + "\n"

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    required_terms = [
        term for term in os.environ.get("FINAL_GATE_REQUIRED_TERMS", "").split("||")
        if term
    ]

    run_dirs = [Path(a) for a in argv if a]
    if not run_dirs:
        print("No run directories supplied. Use: python3 factory_final_gate_audit.py <run_dir> [...]", flush=True)
        return 0

    results = [audit_run(p, required_terms=required_terms) for p in run_dirs]
    report = render_report(results)
    print(report)
    return 0 if all(r["verdict"] == "PASS" for r in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
