# Ireland Health Evidence -- UCC School of Public Health
#
# Every command for this project lives here. Run `make` on its own to list them.
#
# Two ways to run the project, both serving the SAME thing on ONE port:
#   make run     local development, using the .venv virtual environment
#   make up      a container, using docker compose
#
#   http://127.0.0.1:8000        the dashboard
#   http://127.0.0.1:8000/api    the JSON API

SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV      := .venv
PY        := $(VENV)/bin/python
PIP       := $(VENV)/bin/pip
UVICORN   := $(VENV)/bin/uvicorn
PYTEST    := $(VENV)/bin/pytest
RUFF      := $(VENV)/bin/ruff
PORT      := 8000
RUN_DIR   := .run
DB        := data/gbd.db
APP_URL   := http://127.0.0.1:$(PORT)

.PHONY: help setup setup-dev seed reseed run stop restart status smoke open logs \
        test lint format check up down docker-restart docker-logs docker-ps \
        refresh clean distclean wait-api

# Poll until the API answers, rather than guessing how long startup takes.
# Deliberately not `curl --retry`: that gives up on a connection reset, which
# is exactly what Docker's port proxy does while a container is still booting.
wait-api:
	@for i in $$(seq 1 60); do \
		curl -sf --max-time 2 $(APP_URL)/api/health > /dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	exit 1

## ---------------------------------------------------------------- help ----

help: ## Show this help
	@echo ""
	@echo "  Ireland Health Evidence -- UCC School of Public Health"
	@echo ""
	@echo "  First time here?  make setup && make run"
	@echo ""
	@echo "  Run the app (local, using .venv):"
	@grep -E '^(setup|setup-dev|seed|reseed|run|stop|restart|status|open|logs):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Run the app (Docker):"
	@grep -E '^(up|down|docker-restart|docker-logs|docker-ps):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Quality checks:"
	@grep -E '^(test|lint|format|smoke|check):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Data and housekeeping:"
	@grep -E '^(refresh|clean|distclean):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

## ------------------------------------------------------------ the app ----

setup: $(VENV)/.installed ## Create .venv and install runtime dependencies

$(VENV)/.installed: requirements.txt
	@echo "==> Creating virtual environment in $(VENV)"
	@python3 -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pip
	@echo "==> Installing pinned dependencies"
	@$(PIP) install --quiet -r requirements.txt
	@touch $@
	@echo "==> Ready. Python: $$($(PY) -V)"

setup-dev: $(VENV)/.installed-dev ## Also install test and lint tools

$(VENV)/.installed-dev: requirements-dev.txt $(VENV)/.installed
	@echo "==> Installing development dependencies"
	@$(PIP) install --quiet -r requirements-dev.txt
	@touch $@
	@echo "==> Ready. Run: make check"

seed: $(DB) ## Build the database from the seed CSVs (skipped if up to date)

$(DB): $(VENV)/.installed etl/load_seed.py data/gbd_seed.csv data/gbd_ranked_seed.csv
	@echo "==> Seeding database"
	@$(PY) -m etl.load_seed

reseed: setup ## Rebuild the database from scratch
	@rm -f $(DB)
	@$(MAKE) --no-print-directory seed

run: $(DB) ## Start the app in the background
	@$(MAKE) --no-print-directory stop
	@mkdir -p $(RUN_DIR)
	@echo "==> Starting app on :$(PORT)"
	@nohup $(UVICORN) app.main:app --host 127.0.0.1 --port $(PORT) \
		> $(RUN_DIR)/app.log 2>&1 & echo $$! > $(RUN_DIR)/app.pid
	@$(MAKE) --no-print-directory wait-api \
		|| { echo "!! App did not start -- see $(RUN_DIR)/app.log"; exit 1; }
	@echo ""
	@echo "    Dashboard  $(APP_URL)"
	@echo "    API        $(APP_URL)/api      (docs at $(APP_URL)/docs)"
	@echo ""
	@echo "    make logs    follow output      make stop    shut down"
	@echo ""

stop: ## Stop the local app
	@if [ -f $(RUN_DIR)/app.pid ]; then \
		pid=$$(cat $(RUN_DIR)/app.pid); \
		if kill $$pid 2>/dev/null; then echo "==> Stopped app (pid $$pid)"; fi; \
		rm -f $(RUN_DIR)/app.pid; \
	fi

restart: stop run ## Restart the local app

status: ## Show what is listening on the port
	@echo "==> Listening on :$(PORT)"
	@lsof -nP -iTCP:$(PORT) -sTCP:LISTEN 2>/dev/null || echo "    (nothing)"
	@echo "==> Containers"
	@docker compose ps 2>/dev/null || echo "    (docker unavailable)"

open: ## Open the dashboard in a browser
	@open $(APP_URL) 2>/dev/null || echo "Open $(APP_URL)"

logs: ## Follow the local app log
	@tail -f $(RUN_DIR)/app.log

## ------------------------------------------------------------- docker ----

up: ## Build and start the container
	@docker compose up -d --build
	@$(MAKE) --no-print-directory wait-api \
		|| { echo "!! App did not start -- try: make docker-logs"; exit 1; }
	@echo ""
	@echo "    Dashboard  $(APP_URL)"
	@echo "    API        $(APP_URL)/api"
	@echo ""

down: ## Stop and remove the container (frees the port)
	@docker compose down

docker-restart: down up ## Rebuild and restart the container

docker-logs: ## Follow the container log
	@docker compose logs -f

docker-ps: ## Show container status
	@docker compose ps

## ---------------------------------------------------- quality checks ----

test: setup-dev ## Run the test suite
	@$(PYTEST)

lint: setup-dev ## Check formatting and code style
	@$(RUFF) check .
	@$(RUFF) format --check .

format: setup-dev ## Auto-fix formatting and import order
	@$(RUFF) check --fix .
	@$(RUFF) format .

smoke: ## Check a RUNNING app answers on every endpoint
	@echo "==> Smoke testing $(APP_URL)"
	@for path in \
		"/api/health" \
		"/api/meta" \
		"/api/indicators" \
		"/api/trend?indicator=tobacco_sev" \
		"/api/ranked?type=causes" \
		"/api/export.csv?indicator=le" ; do \
		code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$(APP_URL)$$path"); \
		if [ "$$code" = "200" ]; then echo "    ok   $$code  $$path"; \
		else echo "    FAIL $$code  $$path"; fail=1; fi; \
	done; \
	code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$(APP_URL)/"); \
	if [ "$$code" = "200" ]; then echo "    ok   $$code  /  (dashboard)"; \
	else echo "    FAIL $$code  /  (dashboard)"; fail=1; fi; \
	[ -z "$$fail" ] || exit 1

check: lint test ## Run lint and tests -- what CI runs

## --------------------------------------------------- data and cleanup ----

refresh: setup ## Ingest the newest GBD export from data/incoming/
	@./scripts/refresh.sh

clean: ## Remove the database, logs, and caches (keeps .venv)
	@rm -rf $(RUN_DIR) $(DB) .pytest_cache .ruff_cache
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "==> Cleaned. Rebuild the database with: make seed"

distclean: clean ## Also remove the virtual environment
	@rm -rf $(VENV)
	@echo "==> Removed $(VENV). Recreate it with: make setup"
