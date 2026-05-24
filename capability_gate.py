#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import shlex


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class GateDecision:
    kind: str
    target: str
    decision: str
    reason: str
    source: str = "capability_gate"
    raw_decision: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def denied(self) -> bool:
        return self.decision == "deny"

    @property
    def caution(self) -> bool:
        return self.decision == "caution"


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    if any(x in text for x in ("deny", "denied", "block", "blocked", "reject", "forbid")):
        return "deny"
    if any(x in text for x in ("caution", "warn", "warning", "review", "manual")):
        return "caution"
    if any(x in text for x in ("allow", "allowed", "ok", "pass", "safe", "read-only", "readonly")):
        return "allow"
    return "caution"


def _extract(raw: Any) -> tuple[str, str]:
    if raw is None:
        return "caution", "no lower-level decision returned"

    if isinstance(raw, dict):
        for key in ("decision", "risk", "level", "status", "action", "classification", "verdict"):
            if key in raw:
                decision = _norm(raw.get(key))
                reason = raw.get("reason") or raw.get("message") or raw.get("detail") or str(raw)
                return decision, str(reason)
        return _norm(str(raw)), str(raw)

    for key in ("decision", "risk", "level", "status", "action", "classification", "verdict"):
        if hasattr(raw, key):
            decision = _norm(getattr(raw, key))
            reason = getattr(raw, "reason", None) or getattr(raw, "message", None) or str(raw)
            return decision, str(reason)

    if isinstance(raw, tuple) and raw:
        decision = _norm(raw[0])
        reason = raw[1] if len(raw) > 1 else raw[0]
        return decision, str(reason)

    return _norm(raw), str(raw)


def _decision(kind: str, target: str, raw: Any, source: str) -> GateDecision:
    decision, reason = _extract(raw)
    return GateDecision(
        kind=kind,
        target=target,
        decision=decision,
        reason=reason,
        source=source,
        raw_decision=str(raw),
    )


def classify_command(command: str | list[str] | tuple[str, ...]) -> GateDecision:
    if isinstance(command, (list, tuple)):
        target = " ".join(shlex.quote(str(x)) for x in command)
    else:
        target = str(command)

    try:
        import modern_command_guard

        raw = modern_command_guard.classify_command_risk(target)
        return _decision("command", target, raw, "modern_command_guard.classify_command_risk")
    except Exception as exc:
        return GateDecision("command", target, "deny", f"command guard unavailable: {exc}")


def _fallback_path_gate(path: str) -> GateDecision:
    target = str(path)
    try:
        resolved = (ROOT / target).resolve()
    except Exception as exc:
        return GateDecision("path", target, "deny", f"path resolution failed: {exc}")

    if not str(resolved).startswith(str(ROOT)):
        return GateDecision("path", target, "deny", "path is outside the Link repo root")

    rel = resolved.relative_to(ROOT)
    parts = set(rel.parts)

    if ".git" in parts:
        return GateDecision("path", target, "deny", "path is inside .git metadata")
    if ".agents" in parts:
        return GateDecision("path", target, "caution", "path is inside Link agent generated state")
    if "research" in parts:
        return GateDecision("path", target, "caution", "path is research/reference material")

    return GateDecision("path", target, "allow", "path is inside Link repo")


def classify_path(path: str, operation: str = "read") -> GateDecision:
    target = str(path)
    op = str(operation or "read").strip().lower()

    try:
        import modern_file_safety

        file_op = getattr(modern_file_safety, "classify_file_operation", None)
        if file_op:
            raw = file_op(target, operation=op, root=ROOT)
            return _decision("path", target, raw, "modern_file_safety.classify_file_operation")

        for name in (
            "classify_path_risk",
            "classify_file_risk",
            "classify_path_safety",
            "classify_file_safety",
            "check_file_safety",
            "classify_path",
        ):
            fn = getattr(modern_file_safety, name, None)
            if fn:
                try:
                    raw = fn(target)
                except TypeError:
                    raw = fn(Path(target))
                return _decision("path", target, raw, f"modern_file_safety.{name}")
    except Exception:
        pass

    return _fallback_path_gate(target)


def classify_file_operation(path: str, operation: str = "read") -> GateDecision:
    return classify_path(path, operation=operation)


def classify_git_command(command: str | list[str] | tuple[str, ...]) -> GateDecision:
    if isinstance(command, (list, tuple)):
        target = " ".join(shlex.quote(str(x)) for x in command)
    else:
        target = str(command)

    try:
        import modern_git_safety

        for name in (
            "classify_git_command_risk",
            "classify_git_risk",
            "classify_command_risk",
            "classify_git_command",
        ):
            fn = getattr(modern_git_safety, name, None)
            if fn:
                raw = fn(target)
                return _decision("git", target, raw, f"modern_git_safety.{name}")
    except Exception:
        pass

    lowered = target.lower().strip()
    deny_needles = ("reset --hard", "clean -fd", "push --force", "push -f")
    if any(x in lowered for x in deny_needles):
        return GateDecision("git", target, "deny", "destructive git command")
    if lowered.startswith(("git status", "git diff", "git log")):
        return GateDecision("git", target, "allow", "read-only git command")
    if lowered.startswith(("git add", "git commit", "git checkout", "git switch")):
        return GateDecision("git", target, "caution", "git command may modify repo state")
    return classify_command(target)


def classify_request(kind: str, target: str | list[str]) -> GateDecision:
    normalized = str(kind or "").strip().lower()
    if normalized in {"command", "cmd", "shell"}:
        return classify_command(target)
    if normalized in {"path", "file", "filesystem"}:
        return classify_path(str(target))
    if normalized in {"read", "write", "edit", "delete", "remove", "move", "copy"}:
        return classify_path(str(target), operation=normalized)
    if normalized in {"git", "git_command"}:
        return classify_git_command(target)
    return GateDecision(normalized or "unknown", str(target), "deny", "unknown capability kind")


def require_allow(kind: str, target: str | list[str]) -> GateDecision:
    decision = classify_request(kind, target)
    if decision.decision != "allow":
        raise PermissionError(f"{decision.kind} blocked: {decision.decision}: {decision.reason}")
    return decision
