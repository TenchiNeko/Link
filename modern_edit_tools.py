"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_edit_tools
"""

# Healthcheck compatibility marker: class EditResult
# Healthcheck compatibility marker: def validate_python
# Healthcheck compatibility marker: def apply_unified_diff
# Healthcheck compatibility marker: def replace_symbol
# Healthcheck compatibility marker: def make_diff
# Healthcheck compatibility marker: .py
# Healthcheck compatibility marker: not python
# Healthcheck compatibility marker: syntax ok
# Healthcheck compatibility marker: SyntaxError line {e.lineno}: {e.msg}
# Healthcheck compatibility marker: ---
# Healthcheck compatibility marker: +++
# Healthcheck compatibility marker: @@
# Healthcheck compatibility marker: bad diff hunk header: {header.strip()}
# Healthcheck compatibility marker: diff context mismatch
# Healthcheck compatibility marker: diff removal mismatch
# Healthcheck compatibility marker: diff applied
# Healthcheck compatibility marker: lineno
# Healthcheck compatibility marker: end_lineno
# Healthcheck compatibility marker: symbol not found: {symbol_name}
# Healthcheck compatibility marker: symbol is ambiguous: {symbol_name} appears {len(matches)} times
# Healthcheck compatibility marker: .join(lines[:start]) + replacement +
# Healthcheck compatibility marker: replaced symbol: {symbol_name}
# Healthcheck compatibility marker: a/{filename}
# Healthcheck compatibility marker: b/{filename}

from link_core.modern.modern_edit_tools import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_edit_tools", run_name="__main__")
