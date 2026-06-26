# Developer task runner for the conductor.
# Uses a local .venv (python3.12). `make install` bootstraps it.

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install lint fmt fmt-check typecheck test check clean

help:
	@echo "Targets: install  lint  fmt  fmt-check  typecheck  test  check  clean"

$(VENV):
	python3.12 -m venv $(VENV)

install: $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

lint:
	$(VENV)/bin/ruff check .

fmt:
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

fmt-check:
	$(VENV)/bin/ruff format --check .

typecheck:
	$(VENV)/bin/mypy jarvis

test:
	$(VENV)/bin/pytest

# The full gate CI runs.
check: lint fmt-check typecheck test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__
