# Link

[![CI](https://github.com/TenchiNeko/Link/actions/workflows/ci.yml/badge.svg)](https://github.com/TenchiNeko/Link/actions/workflows/ci.yml)

Link is a local-first Python toolkit for supervised agent workflows, guarded research intake, and evidence-backed upgrade planning.

## What is Link?

Link provides one CLI for running bounded agent and operating-mode workflows. It keeps model routing, approval gates, execution receipts, health checks, and research-derived proposals in explicit, inspectable data structures.

The repository currently exposes three operating modes:

- **Base** — canonical routing, roles, safety, diagnostics, and receipts.
- **Growth** — read-only research intake and proposal planning with approval boundaries.
- **Business** — governed business-development and operations previews.

Link is designed for supervised local use. Commands that can write state or apply changes are explicit and approval-gated; previews are the default for research and planning paths.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

python3 link.py --help
python3 link.py config
python3 link.py modes
python3 link.py self-test
```

Python 3.11 or newer is recommended. The default model configuration uses loopback endpoints and does not require credentials for CLI smoke checks.

## Common commands

```bash
python3 link.py status --json       # inspect local runtime endpoints
python3 link.py doctor              # run diagnostics
python3 link.py roles               # list worker profiles
python3 link.py growth --help       # inspect Growth commands
python3 link.py business --help     # inspect Business commands
python3 tests/test_profile_gate.py
python3 tests/test_canonical_architecture.py
python3 tests/test_growth_pipeline.py --suite base
```

Growth research commands accept user-supplied files or directories. External repositories and downloaded archives are intentionally not bundled with Link; use a disposable, local input directory and keep provenance in the resulting review data.

## Configuration

The checked-in configuration surface is in [`configs/`](configs/). Start with [`configs/models.yaml`](configs/models.yaml) and [`configs/teams/`](configs/teams/). Environment-specific values belong in a local `.env` file or the shell environment; `.env` files are ignored by Git.

Useful variables include:

- `OLLAMA_HOST` or `OLLAMA_BASE_URL` for status checks.
- `OLLAMA_PRIMARY_URL` for the primary OpenAI-compatible local model endpoint.
- `LINK_LOCAL_FAST_MODEL` and `LINK_LOCAL_DEEP_MODEL` for local model selection.
- `OPENROUTER_API_KEY` or `LINK_OPENROUTER_API_KEY` for explicitly enabled cloud-advisor paths.
- `LINK_ALLOW_OPENROUTER_ADVISOR=1` to opt into those paths.

See [`.env.example`](.env.example) and [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for safe placeholders and the current configuration boundaries.

## Architecture

```text
link.py              canonical command-line entrypoint
link_core/           routing, roles, safety, receipts, diagnostics
link_modes/          Growth and Business operating modes
factory/             reusable workflow and team configuration helpers
configs/             model and team configuration
tools/research/      Link-native file/research inspection tools
tests/               standalone deterministic smoke suites
```

The architecture is intentionally conservative: source intake produces evidence and proposals, while implementation remains a separate, human-approved step. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the supported boundaries.

## Development

```bash
make install
make test
make lint
make typecheck
```

The test files are standalone smoke suites rather than pytest-discovered unit tests. `make test` invokes the supported commands directly. Some source-archive integration checks require private, user-supplied archives and are opt-in; they are not part of a clean checkout.

## Security

Never commit credentials, browser state, private keys, model dumps, or local runtime receipts. Link reads provider credentials from environment variables and redacts sensitive values in reporting paths. Please see [SECURITY.md](SECURITY.md) for reporting guidance.

## Contributing

Small, focused changes are easiest to review. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

Link is released under the [MIT License](LICENSE).
