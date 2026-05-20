#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

SECRET_KEY_RE = re.compile(r"(token|secret|api[_-]?key|authorization|cookie|password|webhook|bearer)", re.I)
SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(token|secret|api[_-]?key|authorization|cookie|password|webhook)\b\s*([:=])\s*([^\s,'\"]+)"
)


def run_cmd(args: list[str], timeout: int = 10, cwd: Path | None = None) -> dict[str, Any]:
    try:
        p = subprocess.run(
            args,
            cwd=str(cwd or ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": scrub_text(p.stdout.strip()),
            "stderr": scrub_text(p.stderr.strip()),
            "cmd": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": scrub_text((exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""),
            "stderr": f"timeout after {timeout}s",
            "cmd": args,
        }
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": scrub_text(str(exc)), "cmd": args}


def git(*args: str, timeout: int = 10) -> dict[str, Any]:
    return run_cmd(["git", *args], timeout=timeout)


def scrub_text(text: str) -> str:
    if not text:
        return text
    text = SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", text, flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9]{12,}", "sk-<redacted>", text)
    text = re.sub(r"apify_[A-Za-z0-9]{8,}", "apify_<redacted>", text)
    return text


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SECRET_KEY_RE.search(str(k)):
                out[k] = "<redacted>"
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_obj(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def head_commit() -> str | None:
    r = git("rev-parse", "--short", "HEAD")
    return r["stdout"] if r["ok"] else None


def full_head_commit() -> str | None:
    r = git("rev-parse", "HEAD")
    return r["stdout"] if r["ok"] else None


def safe_latest_commit() -> str | None:
    r = git("rev-parse", "--short", "safe-link-latest")
    return r["stdout"] if r["ok"] else None


def git_dirty() -> list[str]:
    r = git("status", "--short", "--untracked-files=all")
    if not r["stdout"]:
        return []
    return [line for line in r["stdout"].splitlines() if line.strip()]


def latest_engine_reports(limit: int = 10) -> list[dict[str, Any]]:
    root = ROOT / ".agents" / "engine_runs"
    if not root.exists():
        return []
    paths = sorted(root.glob("*/engine_report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for path in paths[:limit]:
        data = read_json(path)
        if not data:
            continue
        data["_path"] = str(path)
        out.append(redact_obj(data))
    return out


def latest_engine_report() -> dict[str, Any] | None:
    reports = latest_engine_reports(1)
    return reports[0] if reports else None


def tcp_check(host: str, port: int, timeout: float = 1.0) -> dict[str, Any]:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return {"host": host, "port": port, "reachable": True}
    except Exception as exc:
        return {"host": host, "port": port, "reachable": False, "error": str(exc)}
    finally:
        try:
            s.close()
        except Exception:
            pass


def json_print(data: Any) -> None:
    print(json.dumps(redact_obj(data), indent=2, sort_keys=True))


def human_bool(value: bool) -> str:
    return "OK" if value else "FAIL"


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""
