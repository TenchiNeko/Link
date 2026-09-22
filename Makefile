PYTHON ?= python3
PY_FILES := $(shell git ls-files '*.py')

.PHONY: help install test lint typecheck format-check

help: ## Show available development commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-16s %s\n", $$1, $$2}'

install: ## Install runtime and development dependencies
	$(PYTHON) -m pip install -r requirements.txt

test: ## Run the supported deterministic smoke suites
	$(PYTHON) tests/test_profile_gate.py
	$(PYTHON) tests/test_canonical_architecture.py
	$(PYTHON) tests/test_growth_pipeline.py --suite base
	$(PYTHON) tests/test_growth_pipeline.py --suite source-fast

lint: ## Run fatal Ruff checks across tracked Python files
	$(PYTHON) -m ruff check --select E9,F63,F7,F82 --no-cache $(PY_FILES)

typecheck: ## Type-check the stable runtime status entrypoint
	$(PYTHON) -m mypy --ignore-missing-imports link_status.py

format-check: ## Check formatting for the stable runtime status entrypoint
	$(PYTHON) -m ruff format --check --no-cache link_status.py
