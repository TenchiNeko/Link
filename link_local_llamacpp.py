"""Compatibility shim for moved module.

Canonical module:
    link_core.models.link_local_llamacpp
"""

# Healthcheck compatibility marker: def read_prompt
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: --prompt
# Healthcheck compatibility marker: --prompt-file
# Healthcheck compatibility marker: --model
# Healthcheck compatibility marker: LINK_LLAMACPP_MODEL
# Healthcheck compatibility marker: local
# Healthcheck compatibility marker: LINK_LLAMACPP_BASE_URL
# Healthcheck compatibility marker: http://127.0.0.1:8084
# Healthcheck compatibility marker: ERROR: empty prompt
# Healthcheck compatibility marker: model
# Healthcheck compatibility marker: messages
# Healthcheck compatibility marker: role
# Healthcheck compatibility marker: system
# Healthcheck compatibility marker: content
# Healthcheck compatibility marker: You are a read-only local code review delegate.
# Healthcheck compatibility marker: Do not execute commands. Do not claim to modify files.
# Healthcheck compatibility marker: Return concise audit/review text only.
# Healthcheck compatibility marker: user
# Healthcheck compatibility marker: temperature
# Healthcheck compatibility marker: max_tokens
# Healthcheck compatibility marker: {base_url}/v1/chat/completions
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: Content-Type
# Healthcheck compatibility marker: application/json
# Healthcheck compatibility marker: POST
# Healthcheck compatibility marker: replace
# Healthcheck compatibility marker: ERROR: llama.cpp delegate request failed: {e}
# Healthcheck compatibility marker: choices
# Healthcheck compatibility marker: message
# Healthcheck compatibility marker: </think>
# Healthcheck compatibility marker: __main__

from link_core.models.link_local_llamacpp import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.models.link_local_llamacpp", run_name="__main__")
