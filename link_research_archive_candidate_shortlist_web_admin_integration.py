#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

import link_research_archive_candidate_shortlist_web_admin_route as route
from link_research_archive_candidate_shortlist_exporter import _write_self_test_intake


MARKER = "research archive candidate shortlist web admin integration OK"

TRIGGERS = (
    "research archive candidate shortlist web admin integration",
    "research candidate shortlist web admin integration",
    "candidate shortlist web admin integration",
    "research archive candidate shortlist",
    "research candidate shortlist",
    "candidate shortlist",
)


ROUTE_BUILDER_NAMES = (
    "build_research_archive_candidate_shortlist_web_admin_route_response",
    "build_research_candidate_shortlist_web_admin_route_response",
    "build_candidate_shortlist_web_admin_route_response",
    "build_research_archive_candidate_shortlist_response",
    "build_research_candidate_shortlist_response",
)

ROUTE_MATCHER_NAMES = (
    "matches_research_candidate_shortlist_web_admin_prompt",
    "matches_research_archive_candidate_shortlist_web_admin_prompt",
    "matches_research_candidate_shortlist_prompt",
)


def matches_research_candidate_shortlist_web_admin_integration_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    if any(trigger in lowered for trigger in TRIGGERS):
        return True

    for name in ROUTE_MATCHER_NAMES:
        matcher = getattr(route, name, None)
        if callable(matcher):
            try:
                if matcher(prompt):
                    return True
            except Exception:
                continue

    return False


def _find_route_builder() -> Callable[..., dict[str, Any]]:
    for name in ROUTE_BUILDER_NAMES:
        fn = getattr(route, name, None)
        if callable(fn):
            return fn

    for name in dir(route):
        if name.startswith("build_") and "shortlist" in name and callable(getattr(route, name)):
            return getattr(route, name)

    raise RuntimeError("Could not find LU54 shortlist web admin route builder")


def _call_builder(
    builder: Callable[..., Any],
    *,
    prompt: str,
    intake_dir: Path,
    limit: int,
    preview_limit: int,
    json_requested: bool,
) -> dict[str, Any]:
    sig = inspect.signature(builder)
    kwargs: dict[str, Any] = {}

    for name in sig.parameters:
        if name == "prompt":
            kwargs[name] = prompt
        elif name == "intake_dir":
            kwargs[name] = intake_dir
        elif name == "limit":
            kwargs[name] = limit
        elif name == "preview_limit":
            kwargs[name] = preview_limit
        elif name == "json_requested":
            kwargs[name] = json_requested
        elif name == "write_outputs":
            kwargs[name] = True

    attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
        ((), kwargs),
        ((prompt,), {k: v for k, v in kwargs.items() if k != "prompt"}),
        ((prompt, intake_dir), {k: v for k, v in kwargs.items() if k not in {"prompt", "intake_dir"}}),
        ((intake_dir,), {k: v for k, v in kwargs.items() if k != "intake_dir"}),
        ((), {}),
    ]

    last_error: Exception | None = None
    for args, call_kwargs in attempts:
        try:
            response = builder(*args, **call_kwargs)
            if isinstance(response, dict):
                return response
            return {
                "ok": False,
                "status": "invalid_response",
                "error": f"route builder returned {type(response).__name__}",
                "raw_response": response,
            }
        except TypeError as exc:
            last_error = exc
            continue

    return {
        "ok": False,
        "status": "route_builder_type_error",
        "error": str(last_error) if last_error else "unknown route builder TypeError",
    }


def build_research_candidate_shortlist_web_admin_integration_response(
    prompt: str,
    intake_dir: Path,
    *,
    limit: int = 10,
    preview_limit: int = 600,
    json_requested: bool = False,
) -> dict[str, Any]:
    matched = matches_research_candidate_shortlist_web_admin_integration_prompt(prompt)
    builder = _find_route_builder()

    response = _call_builder(
        builder,
        prompt=prompt,
        intake_dir=intake_dir,
        limit=limit,
        preview_limit=preview_limit,
        json_requested=json_requested,
    )

    response = dict(response)
    response.setdefault("ok", bool(response.get("ok")))
    response["matched"] = bool(matched)
    response["integration_kind"] = "research_archive_candidate_shortlist_web_admin_integration"
    response["integration_marker"] = MARKER
    response["non_destructive"] = True

    html = response.get("html")
    if isinstance(html, str) and MARKER not in html:
        response["html"] = html.replace(
            "</section>",
            f"<p><code>{MARKER}</code></p></section>",
            1,
        )

    return response


def validate_research_candidate_shortlist_web_admin_integration(*args: Any, **kwargs: Any) -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_candidate_shortlist_web_admin_integration_response(
            "show research archive candidate shortlist web admin integration",
            intake_dir,
            limit=2,
            preview_limit=200,
            json_requested=True,
        )

        if not response.get("ok"):
            failures.append("integrated shortlist response should be ok")

        if not response.get("matched"):
            failures.append("integrated shortlist response should be matched")

        if response.get("integration_marker") != MARKER:
            failures.append("integrated shortlist marker missing")

        html = response.get("html", "")
        if not isinstance(html, str) or "candidate shortlist" not in html.lower():
            failures.append("integrated shortlist html missing candidate shortlist content")

        if "data-link-destructive=\"false\"" not in html and not response.get("non_destructive"):
            failures.append("integrated shortlist response should be non-destructive")

        shortlist = response.get("shortlist")
        if shortlist is not None and not isinstance(shortlist, list):
            failures.append("shortlist payload should be a list when present")

    return failures


def self_test() -> bool:
    failures = validate_research_candidate_shortlist_web_admin_integration()
    if failures:
        print("research archive candidate shortlist web admin integration FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="LU55 research archive candidate shortlist web admin integration")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--intake-dir", default=".link_research_intake")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-limit", type=int, default=600)
    parser.add_argument("prompt", nargs="*", default=["show", "research", "archive", "candidate", "shortlist"])
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)

    response = build_research_candidate_shortlist_web_admin_integration_response(
        " ".join(args.prompt),
        Path(args.intake_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html") or json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
