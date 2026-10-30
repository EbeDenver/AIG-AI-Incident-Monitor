# ==============================================================================
# AI Incident Monitor - Developer Workflow Makefile
# ==============================================================================

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PYTEST ?= $(VENV)/bin/pytest
ALEMBIC ?= $(VENV)/bin/alembic
RUFF ?= $(VENV)/bin/ruff
MYPY ?= $(VENV)/bin/mypy

.PHONY: help test test-unit test-integration migrate migrate-down db-up db-down lint format typecheck clean purge-raw-feeds purge-raw-feeds-dry-run import-oecd verify-provenance-chain verify-provenance-chain-dry-run diagnose diagnose-json

help:
	@echo "Available Makefile targets:"
	@echo "  test              Run full test suite (Phase 2 domain + Phase 3 persistence/import)"
	@echo "  test-unit         Run unit test suite"
	@echo "  test-integration  Run migration and import integration tests"
	@echo "  migrate           Run Alembic migrations to head"
	@echo "  migrate-down      Downgrade Alembic migrations by 1 revision"
	@echo "  db-up             Start PostgreSQL container via docker-compose"
	@echo "  db-down           Stop PostgreSQL container via docker-compose"
	@echo "  lint              Run ruff linter on backend package"
	@echo "  format            Run ruff code formatter on backend package"
	@echo "  typecheck         Run mypy static type analysis"
	@echo "  clean             Clean local test and build artifacts"

test:
	$(PYTEST) backend/tests

test-unit:
	$(PYTEST) backend/tests/unit

test-integration:
	$(PYTEST) backend/tests/integration

migrate:
	cd backend && ../$(ALEMBIC) upgrade head

migrate-down:
	cd backend && ../$(ALEMBIC) downgrade -1

db-up:
	docker compose -f backend/docker-compose.yml up -d

db-down:
	docker compose -f backend/docker-compose.yml down

lint:
	$(PYTHON) -m ruff check backend/

format:
	$(PYTHON) -m ruff format backend/

typecheck:
	$(PYTHON) -m mypy backend/src/ai_incident_monitor

clean:
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +

purge-raw-feeds:
	$(PYTHON) -m ai_incident_monitor.ingestion.purge

purge-raw-feeds-dry-run:
	$(PYTHON) -m ai_incident_monitor.ingestion.purge --dry-run

import-oecd:
	$(PYTHON) -m ai_incident_monitor.ingestion.oecd_adapter --file $(FILE)

verify-provenance-chain:
	$(PYTHON) -m ai_incident_monitor.ingestion.verify_chain_cli

verify-provenance-chain-dry-run:
	$(PYTHON) -m ai_incident_monitor.ingestion.verify_chain_cli --dry-run

diagnose:
	$(PYTHON) -m ai_incident_monitor.diagnostics.cli

diagnose-json:
	$(PYTHON) -m ai_incident_monitor.diagnostics.cli --json

