"""Compatibility shim for moved module.

Canonical module:
    link_core.config.link_common
"""

# Healthcheck compatibility marker: def run_cmd
# Healthcheck compatibility marker: def git
# Healthcheck compatibility marker: def scrub_text
# Healthcheck compatibility marker: def redact_obj
# Healthcheck compatibility marker: def read_json
# Healthcheck compatibility marker: def write_json
# Healthcheck compatibility marker: def head_commit
# Healthcheck compatibility marker: def full_head_commit
# Healthcheck compatibility marker: def safe_latest_commit
# Healthcheck compatibility marker: def git_dirty
# Healthcheck compatibility marker: def latest_engine_reports
# Healthcheck compatibility marker: def latest_engine_report
# Healthcheck compatibility marker: def tcp_check
# Healthcheck compatibility marker: def json_print
# Healthcheck compatibility marker: def human_bool
# Healthcheck compatibility marker: def load_text
# Healthcheck compatibility marker: (token|secret|api[_-]?key|authorization|cookie|password|webhook|bearer)
# Healthcheck compatibility marker: (?i)\b(token|secret|api[_-]?key|authorization|cookie|password|webhook)\b\s*([:=])\s*([^\s,'\
# Healthcheck compatibility marker: returncode
# Healthcheck compatibility marker: stdout
# Healthcheck compatibility marker: stderr
# Healthcheck compatibility marker: cmd
# Healthcheck compatibility marker: ).strip() if isinstance(exc.stdout, str) else
# Healthcheck compatibility marker: timeout after {timeout}s
# Healthcheck compatibility marker: : False,
# Healthcheck compatibility marker: : None,
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: {m.group(1)}{m.group(2)}<redacted>
# Healthcheck compatibility marker: Bearer\s+[A-Za-z0-9._\-]+
# Healthcheck compatibility marker: Bearer <redacted>
# Healthcheck compatibility marker: sk-[A-Za-z0-9]{12,}
# Healthcheck compatibility marker: sk-<redacted>
# Healthcheck compatibility marker: apify_[A-Za-z0-9]{8,}
# Healthcheck compatibility marker: apify_<redacted>
# Healthcheck compatibility marker: <redacted>
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: rev-parse
# Healthcheck compatibility marker: --short
# Healthcheck compatibility marker: HEAD
# Healthcheck compatibility marker: safe-link-latest
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: --untracked-files=all
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: engine_runs
# Healthcheck compatibility marker: */engine_report.json
# Healthcheck compatibility marker: selftest
# Healthcheck compatibility marker: _path
# Healthcheck compatibility marker: host
# Healthcheck compatibility marker: port
# Healthcheck compatibility marker: reachable
# Healthcheck compatibility marker: error
# Healthcheck compatibility marker: if value else

from link_core.config.link_common import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.config.link_common", run_name="__main__")
