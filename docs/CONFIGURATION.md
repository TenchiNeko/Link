# Configuration

Link keeps safe defaults in `configs/models.yaml` and `configs/teams/`. Validate the checked-in configuration with:

```bash
python3 link.py config
```

## Local model endpoints

The default endpoint values use loopback. Set `OLLAMA_HOST` or `OLLAMA_BASE_URL` for status checks, and `OLLAMA_PRIMARY_URL` for the primary OpenAI-compatible model endpoint. Use environment variables for machine-specific hosts, ports, model IDs, and hardware choices.

## Optional cloud advisor

Cloud advisor paths are opt-in. Set `LINK_ALLOW_OPENROUTER_ADVISOR=1` and provide `OPENROUTER_API_KEY` (or the compatibility variable `LINK_OPENROUTER_API_KEY`) only when that behavior is intentional. Never place a real key in YAML, source, documentation, or tests.

## Configuration examples

`.env.example` contains fake placeholders. Copy it to a local `.env` only when needed; `.env` files are ignored by Git. Configuration validation and smoke checks do not require a provider credential.
