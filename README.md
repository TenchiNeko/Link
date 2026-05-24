# Link

Link is the working repository for building and improving Brandon's own local agent/orchestration system.

The Hermes Agent package in `research/agent_research.zip` was used as research material to mine for useful architecture ideas, safety patterns, tool-handling concepts, and possible upgrades. It is not being adopted wholesale as Link.

This repository is being used to keep research notes, smoke test results, integration findings, and safety observations so useful ideas can be selectively adapted into Link.

## Current status

The Hermes Agent source was extracted and tested in an isolated temporary directory, not directly inside the Link repo.

Tested source:

- `research/agent_research.zip`

Extracted test path:

- `/tmp/link-hermes-agent-test.t4WUtf/hermes-agent-main`

Smoke test report:

- `research/hermes_agent_smoke_test_result.md`

The initial Hermes Agent smoke test result has been committed and pushed.

Current pushed commit:

- `2dc7876 docs: add Hermes agent smoke test result`

## What was verified

The Hermes Agent package was tested in an isolated Python virtual environment.

Verified items:

- Python virtual environment creation worked.
- Core and dev dependency install worked inside the extracted Hermes project.
- `run_agent.py --help` worked after dependencies were installed.
- A small safe pytest batch passed.
- File toolset smoke test worked.
- Terminal toolset smoke test worked.
- Combined file plus terminal toolset worked when the comma-separated toolset argument was quoted.

Selected test result:

    113 passed in 1.70s

## Important findings

### 1. Keep Hermes isolated for now

Hermes was tested from the extracted temp path, not installed into the Link repo.

Do not run Hermes install commands from `~/link`, because Link itself is not the Hermes Python project.

This command failed when accidentally run from `~/link`:

    python -m pip install -e .[dev]

Reason:

    ~/link does not contain setup.py or pyproject.toml

### 2. Missing websockets dependency

During tool listing, this warning appeared:

    Could not import tool module tools.browser_dialog_tool: No module named websockets

Installing websockets inside the temp Hermes virtual environment fixed that import warning:

    python -m pip install websockets

This suggests `websockets` may need to be added to the correct Hermes dependency group if browser dialog support is expected.

### 3. Safe toolset is non-writing and non-terminal

The safe toolset loaded only `vision_analyze` in the tested environment because other safe tools failed requirement checks.

The agent could not write files or run shell commands under the safe toolset.

That is expected and useful from a safety standpoint.

### 4. File toolset works

The file toolset loaded:

- `patch`
- `read_file`
- `search_files`
- `write_file`

It successfully created:

    /tmp/hermes-agent-sandbox/hello.txt

With content:

    Hermes smoke test passed

### 5. Terminal toolset works

The terminal toolset loaded:

- `process`
- `terminal`

It successfully printed the current directory and created:

    /tmp/hermes-agent-sandbox/terminal-test.txt

With content:

    Terminal tool worked.

### 6. Combined file and terminal toolsets need quoting

This failed:

    python run_agent.py --enabled_toolsets=file,terminal

Error:

    AttributeError: tuple object has no attribute split

This worked:

    python run_agent.py --enabled_toolsets="file,terminal"

Likely issue:

- Python Fire parses the unquoted comma-separated value into a tuple.
- `run_agent.py` expects a string and calls `.split(",")`.

Suggested future patch:

- Normalize `enabled_toolsets` and `disabled_toolsets` if they arrive as tuple or list before calling `.split(",")`.

## Reproduction notes

From the extracted Hermes project directory:

    cd /tmp/link-hermes-agent-test.t4WUtf/hermes-agent-main
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -e .[dev]
    python -m pip install websockets

Run help:

    PYTHONDONTWRITEBYTECODE=1 python run_agent.py --help | head -80

Run safe tool listing:

    PYTHONDONTWRITEBYTECODE=1 python run_agent.py --list_tools=True --enabled_toolsets=safe --max_turns=1

Run file smoke test:

    mkdir -p /tmp/hermes-agent-sandbox

    PYTHONDONTWRITEBYTECODE=1 python run_agent.py \
      --query="Create /tmp/hermes-agent-sandbox/hello.txt with exactly this text: Hermes smoke test passed" \
      --enabled_toolsets=file \
      --max_turns=4 \
      --verbose=True

    cat /tmp/hermes-agent-sandbox/hello.txt

Run terminal smoke test:

    PYTHONDONTWRITEBYTECODE=1 python run_agent.py \
      --query="Run a harmless command to print the current directory, then create /tmp/hermes-agent-sandbox/terminal-test.txt containing Terminal tool worked." \
      --enabled_toolsets=terminal \
      --max_turns=4 \
      --verbose=True

    cat /tmp/hermes-agent-sandbox/terminal-test.txt

Run combined file plus terminal smoke test:

    rm -rf /tmp/hermes-agent-sandbox/combo-test
    mkdir -p /tmp/hermes-agent-sandbox/combo-test

    PYTHONDONTWRITEBYTECODE=1 python run_agent.py \
      --query="Use only /tmp/hermes-agent-sandbox/combo-test. Create a file named input.txt with the text alpha, read it back, then create summary.txt saying read succeeded. Do not touch any other folder." \
      --enabled_toolsets="file,terminal" \
      --max_turns=6 \
      --verbose=True

    find /tmp/hermes-agent-sandbox/combo-test -maxdepth 1 -type f -print -exec cat {} \;

## Safety notes before deeper integration

Before integrating Hermes into Link more directly:

1. Review command execution boundaries.
2. Review file write and patch permissions.
3. Confirm how tools are gated by toolset.
4. Confirm whether terminal commands run in the intended sandbox or host context.
5. Confirm credential redaction and logging behavior.
6. Patch the comma-separated toolset tuple issue.
7. Add any missing dependencies, including `websockets`, to the right dependency group.
8. Keep all experiments isolated until the security model is understood.

## GitHub

Remote:

    git@github.com:TenchiNeko/Link.git

Main branch:

    main

Future pushes should work with:

    git push
