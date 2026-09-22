# Contributing to Link

Thanks for helping improve Link. Keep contributions narrow, reproducible, and easy to audit.

## Before opening a pull request

1. Read the relevant code path and existing smoke checks.
2. Do not add downloaded repositories, archives, credentials, runtime receipts, or generated output.
3. Run the smallest relevant checks, then run `make test` when practical.
4. Explain behavior changes, safety implications, and any new configuration in the pull request.

## Development commands

```bash
python3 -m pip install -r requirements.txt
make test
make lint
make typecheck
```

The project uses standalone deterministic smoke suites. New non-trivial behavior should leave one runnable check behind, preferably in the smallest existing suite that covers the behavior.

## Research and external code

Research inputs are local and disposable. Do not commit cloned projects or copied implementation. If a change incorporates third-party code, record its provenance and license obligations before submitting it.

## Pull requests

Describe the problem, the smallest effective change, validation performed, and any known limitations. Avoid claiming support for providers, platforms, or workflows that were not tested.
