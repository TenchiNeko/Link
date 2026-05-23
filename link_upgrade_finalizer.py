#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import pprint
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "link_upgrade_registry.py"
HEALTHCHECK = ROOT / "link_healthcheck.py"
UPGRADES_DOC = ROOT / "UPGRADES.md"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def git_status_paths() -> list[str]:
    out = run(["git", "status", "--porcelain"], check=True).stdout
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def require_repo_root() -> None:
    top = run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    if Path(top).resolve() != ROOT:
        raise SystemExit(f"STOP: expected git root {ROOT}, got {top}")


def require_clean_or_only(allowed: set[str]) -> None:
    dirty = git_status_paths()
    unexpected = [p for p in dirty if p not in allowed]
    if unexpected:
        print("STOP: unexpected dirty files:")
        for p in unexpected:
            print(f"- {p}")
        raise SystemExit(1)


def import_registry() -> Any:
    spec = importlib.util.spec_from_file_location("link_upgrade_registry_live", REGISTRY)
    if spec is None or spec.loader is None:
        raise SystemExit("STOP: could not load link_upgrade_registry.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_assignment(source: str, name: str, value: Any) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(True)
    rendered = f"{name} = {pprint.pformat(value, width=96, sort_dicts=False)}\n"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                start = node.lineno - 1
                end = node.end_lineno
                return "".join(lines[:start] + [rendered] + lines[end:])
    raise SystemExit(f"STOP: could not find assignment {name}")


def marker_key_from(upgrades: list[dict[str, Any]]) -> str:
    for item in reversed(upgrades):
        for key in item:
            low = str(key).lower()
            if "healthcheck" in low and "marker" in low:
                return str(key)
    return "healthcheck_markers"


def next_upgrade_id(upgrade_id: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", upgrade_id)
    if not match:
        return "NEXT"
    prefix, number = match.groups()
    return f"{prefix}{int(number) + 1:0{len(number)}d}"


def patch_registry(
    upgrade_id: str,
    title: str,
    marker: str,
    next_id: str | None,
    next_title: str | None,
) -> None:
    reg = import_registry()
    upgrades = [dict(u) for u in reg.UPGRADES]
    key = marker_key_from(upgrades)

    found = False
    for item in upgrades:
        if item.get("id") == upgrade_id:
            item["status"] = "implemented"
            item["title"] = title
            item[key] = marker
            found = True

    if not found:
        template_keys = list(upgrades[-1].keys()) if upgrades else ["id", "status", "title", key]
        item: dict[str, Any] = {}
        for template_key in template_keys:
            if template_key == "id":
                item[template_key] = upgrade_id
            elif template_key == "status":
                item[template_key] = "implemented"
            elif template_key == "title":
                item[template_key] = title
            elif template_key == key:
                item[template_key] = marker
            else:
                item[template_key] = ""
        upgrades.append(item)

    next_upgrade = {
        "id": next_id or next_upgrade_id(upgrade_id),
        "status": "planned",
        "title": next_title or "Next Link upgrade",
    }

    source = REGISTRY.read_text()
    source = replace_assignment(source, "UPGRADES", upgrades)
    source = replace_assignment(source, "NEXT_UPGRADE", next_upgrade)
    REGISTRY.write_text(source)


def function_name(upgrade_id: str, title: str) -> str:
    raw = f"check_{upgrade_id}_{title}".lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not raw.startswith("check_"):
        raw = "check_" + raw
    return raw


def patch_healthcheck(upgrade_id: str, title: str, marker: str, self_test: str | None) -> None:
    source = HEALTHCHECK.read_text()
    fn = function_name(upgrade_id, title)

    if marker not in source:
        command = self_test or f"{sys.executable} -m py_compile link_upgrade_finalizer.py"
        args_repr = repr(shlex.split(command))
        block = f"""

def {fn}() -> None:
    import subprocess
    subprocess.check_call({args_repr})
    print({marker!r})
"""

        main_index = source.find("\ndef main()")
        if main_index == -1:
            raise SystemExit("STOP: could not find def main() in link_healthcheck.py")
        source = source[:main_index] + block + source[main_index:]

    call = f"    {fn}()\n"
    if call not in source:
        anchor = "    check_file_safety()\n"
        if anchor not in source:
            raise SystemExit("STOP: could not find check_file_safety anchor in healthcheck main()")
        source = source.replace(anchor, call + anchor, 1)

    HEALTHCHECK.write_text(source)


def patch_upgrades_doc(upgrade_id: str, title: str, marker: str) -> None:
    if not UPGRADES_DOC.exists():
        UPGRADES_DOC.write_text("# Link upgrades\n")

    source = UPGRADES_DOC.read_text()
    if upgrade_id in source and title in source:
        return

    entry = (
        f"\n## {upgrade_id} - {title}\n"
        f"- Status: implemented\n"
        f"- Healthcheck marker: {marker}\n"
    )
    UPGRADES_DOC.write_text(source.rstrip() + "\n" + entry)


def run_self_test() -> None:
    assert next_upgrade_id("LU22") == "LU23"
    assert function_name("LU22", "Upgrade finalizer and safe apply workflow").startswith("check_lu22")
    reg = import_registry()
    assert isinstance(reg.UPGRADES, list)
    assert isinstance(reg.NEXT_UPGRADE, dict)
    print("upgrade finalizer OK")


def finalize(args: argparse.Namespace) -> None:
    require_repo_root()

    allowed = {
        args.module,
        "link_upgrade_finalizer.py",
        "link_healthcheck.py",
        "link_upgrade_registry.py",
        "UPGRADES.md",
    }
    require_clean_or_only(allowed)

    module_path = ROOT / args.module
    if not module_path.exists():
        raise SystemExit(f"STOP: module does not exist: {args.module}")

    run([sys.executable, "-m", "py_compile", args.module])
    if args.self_test:
        run(shlex.split(args.self_test))

    patch_registry(args.id, args.title, args.marker, args.next_id, args.next_title)
    patch_healthcheck(args.id, args.title, args.marker, args.self_test)
    patch_upgrades_doc(args.id, args.title, args.marker)

    run([sys.executable, "-m", "py_compile", "link_healthcheck.py", "link_upgrade_registry.py", args.module])
    run([sys.executable, "link_upgrade_registry.py"])
    run([sys.executable, "link_healthcheck.py"])

    paths = ["link_upgrade_finalizer.py", "link_healthcheck.py", "link_upgrade_registry.py", "UPGRADES.md"]
    if args.module not in paths:
        paths.append(args.module)

    run(["git", "add", *paths])

    if not run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        message = args.commit_message or f"feat: add {args.title.lower()} {args.id}"
        run(["git", "commit", "-m", message])
    else:
        print("nothing staged; no commit created")

    run(["git", "tag", "-f", "safe-link-latest"])
    print("upgrade finalizer OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--module", default="link_upgrade_finalizer.py")
    parser.add_argument("--self-test-command", "--self-test-cmd", "--run-self-test", dest="self_test")
    parser.add_argument("--marker")
    parser.add_argument("--next-id")
    parser.add_argument("--next-title")
    parser.add_argument("--commit-message")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    missing = [name for name in ("id", "title", "marker") if not getattr(args, name)]
    if missing:
        raise SystemExit("STOP: missing required args: " + ", ".join(missing))

    finalize(args)


if __name__ == "__main__":
    main()
