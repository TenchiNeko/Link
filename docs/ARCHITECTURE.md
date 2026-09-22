# Architecture

Link is a Python CLI with a local-first, supervised workflow model.

## Boundaries

- `link.py` is the canonical command dispatcher.
- `link_core/` owns shared routing, worker roles, safety classification, diagnostics, receipts, and control-plane contracts.
- `link_modes/growth/` turns user-supplied research into bounded evidence and proposal previews. It does not ship external source repositories.
- `link_modes/business/` provides governed business-development and operations previews.
- `factory/` contains reusable team and workflow helpers.
- `configs/` contains checked-in model and team defaults.
- `tools/research/` contains Link-native inspection utilities.
- `tests/` contains deterministic standalone smoke suites.

## Safety model

Read-only previews are the default. Writes, proposal approvals, patch application, workspace lifecycle actions, and provider opt-ins are represented by explicit commands and guarded boundaries. Runtime receipts and local agent state are deliberately excluded from source control.

## External research

Research archives may be supplied locally when a workflow requires them. They are inputs, not dependencies of the Link source tree. A public checkout must remain useful without them, and any retained observation must preserve provenance without copying upstream implementation.
