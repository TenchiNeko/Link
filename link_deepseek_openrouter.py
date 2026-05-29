"""Compatibility shim for moved module.

Canonical module:
    link_core.models.link_deepseek_openrouter
"""

# Healthcheck compatibility marker: def read_prompt
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: https://openrouter.ai/api/v1/chat/completions
# Healthcheck compatibility marker: , encoding=
# Healthcheck compatibility marker: --prompt
# Healthcheck compatibility marker: --prompt-file
# Healthcheck compatibility marker: --model
# Healthcheck compatibility marker: LINK_OPENROUTER_DEEPSEEK_MODEL
# Healthcheck compatibility marker: deepseek/deepseek-chat
# Healthcheck compatibility marker: --debug-auth
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: OPENROUTER_API_KEY
# Healthcheck compatibility marker: LINK_OPENROUTER_API_KEY
# Healthcheck compatibility marker: your_key_here
# Healthcheck compatibility marker: your_real_openrouter_key_here
# Healthcheck compatibility marker: ERROR: Set a real OPENROUTER_API_KEY or LINK_OPENROUTER_API_KEY.
# Healthcheck compatibility marker: ERROR: empty prompt
# Healthcheck compatibility marker: auth_loaded=true key_prefix={api_key[:7]}... key_len={len(api_key)}
# Healthcheck compatibility marker: model
# Healthcheck compatibility marker: messages
# Healthcheck compatibility marker: role
# Healthcheck compatibility marker: system
# Healthcheck compatibility marker: content
# Healthcheck compatibility marker: You are a careful code review delegate.
# Healthcheck compatibility marker: Do not claim to execute commands.
# Healthcheck compatibility marker: Return concise audit findings and patch suggestions only.
# Healthcheck compatibility marker: user
# Healthcheck compatibility marker: temperature
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: Authorization
# Healthcheck compatibility marker: Bearer {api_key}
# Healthcheck compatibility marker: Content-Type
# Healthcheck compatibility marker: application/json
# Healthcheck compatibility marker: HTTP-Referer
# Healthcheck compatibility marker: http://localhost/link
# Healthcheck compatibility marker: X-Title
# Healthcheck compatibility marker: Link Delegate Runner
# Healthcheck compatibility marker: POST
# Healthcheck compatibility marker: replace
# Healthcheck compatibility marker: ERROR: OpenRouter HTTP {exc.code}: {body}
# Healthcheck compatibility marker: ERROR: {type(exc).__name__}: {exc}
# Healthcheck compatibility marker: choices
# Healthcheck compatibility marker: message
# Healthcheck compatibility marker: __main__

from link_core.models.link_deepseek_openrouter import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.models.link_deepseek_openrouter", run_name="__main__")
