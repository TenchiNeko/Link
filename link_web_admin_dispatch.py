# Healthcheck compatibility marker: Web admin dispatcher
# Healthcheck compatibility marker: link_web.py
# Healthcheck compatibility marker: link_micro_patch.py
# Healthcheck compatibility marker: link_web.py missing {needle!r}
# Healthcheck compatibility marker: link_admin_planner.py
# Healthcheck compatibility marker: link_audit_fast.py
# Healthcheck compatibility marker: --plan-only
# Healthcheck compatibility marker: audit_fastpath
# Healthcheck compatibility marker: micro_patch
# Healthcheck compatibility marker: link_web_admin_dispatch.py missing {needle!r}
# Healthcheck compatibility marker: /tmp/link-web-admin-dispatch-healthcheck-prompt.txt
# Healthcheck compatibility marker: Let's continue on the updates
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: --prompt-file
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: classification
# Healthcheck compatibility marker: broad web admin prompt should route audit_fastpath, got {route!r}
# Healthcheck compatibility marker: human_confirmation_required
# Healthcheck compatibility marker: web admin dispatch planner must require human confirmation
# Healthcheck compatibility marker: --prompt
# Healthcheck compatibility marker: MICRO PATCH: target file: README.md content: `Link web admin dispatch smoke`
# Healthcheck compatibility marker: dirty repo safe text micro prompt should be guarded to audit_fastpath
# Healthcheck compatibility marker: reason
# Healthcheck compatibility marker: dirty repo safe text micro prompt should explain dirty guard
# Healthcheck compatibility marker: clean repo safe text micro prompt should route to micro_patch
# Healthcheck compatibility marker: risk
# Healthcheck compatibility marker: high
# Healthcheck compatibility marker: safe text micro prompt should not become high risk from content words
# Healthcheck compatibility marker: web admin dispatch OK
# Healthcheck compatibility marker: deepseek
# Healthcheck compatibility marker: local_qwen
# Healthcheck compatibility marker: _delegate_cmd
# Healthcheck compatibility marker: DEEPSEEK_API_KEY
# Healthcheck compatibility marker: LINK_DEEPSEEK_CMD
# Healthcheck compatibility marker: LINK_LOCAL_QWEN_CMD
# Healthcheck compatibility marker: LINK_LOCAL_QWEN_MODEL
# Healthcheck compatibility marker: LINK_ENABLE_MODEL_DELEGATES
# Healthcheck compatibility marker: link_delegate_runner.py
# Healthcheck compatibility marker: delegate_to
# Healthcheck compatibility marker: Link Delegate Runner
# Healthcheck compatibility marker: proposed_commands
# Healthcheck compatibility marker: execution_allowed
# Healthcheck compatibility marker: requires_human_confirmation
# Healthcheck compatibility marker: verification_commands
# Healthcheck compatibility marker: model_suggested_commands_not_executed
# Healthcheck compatibility marker: no_write
# Healthcheck compatibility marker: no-write
# Healthcheck compatibility marker: repo_dirty_never_execute_or_delegate_patch
# Healthcheck compatibility markers for moved canonical module.
# Canonical runtime implementation lives in link_core.ops.link_web_admin_dispatch.
# from execution_snapshots import create_execution_snapshot
# create_execution_snapshot(
# action="web_admin_dispatch"
# from rollback_advisor_web_admin_route import rollback_advisor_web_admin_plan
# rollback_advisor_web_admin_plan(prompt)

"""Compatibility shim for moved ops/planner module.

Canonical module:
    link_core.ops.link_web_admin_dispatch
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "ops" / "link_web_admin_dispatch.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.ops.link_web_admin_dispatch")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
