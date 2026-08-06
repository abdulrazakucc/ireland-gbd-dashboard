# Ireland GBD Dashboard -- UCC School of Public Health
#
# Short commands for the whole pipeline. Run `make` on its own to see them.
#
# Two ways to run this project:
#   make run     local development, using the .venv virtual environment
#   make up      a container, using docker compose
#
# Both serve the same thing on ONE port -- http://127.0.0.1:8000 is the
# dashboard, http://127.0.0.1:8000/api/... is the JSON API.

SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV       := .venv
PY         := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
UVICORN    := $(VENV)/bin/uvicorn
PORT       := 8000
RUN_DIR    := .run
DB         := app/gbd.db
# One process serves the dashboard and the API on a single port.
APP_URL    := http://127.0.0.1:$(PORT)
API_URL    := $(APP_URL)

.PHONY: help setup seed reseed run stop restart status smoke open logs \
        up down docker-restart docker-logs docker-ps refresh clean distclean \
        wait-api

# Poll until the API answers, rather than guessing how long startup takes.
# Deliberately not `curl --retry`: that gives up on a connection reset, which
# is exactly what Docker's port proxy does while a container is still booting.
wait-api:
	@for i in $$(seq 1 60); do \
		curl -sf --max-time 2 $(API_URL)/api/health > /dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	exit 1

## ---------------------------------------------------------------- help ----

help: ## Show this help
	@echo ""
	@echo "  Ireland GBD Dashboard -- UCC School of Public Health"
	@echo ""
	@echo "  Local development (venv):"
	@grep -E '^(setup|seed|reseed|run|stop|restart|status|smoke|open|logs):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Docker:"
	@grep -E '^(up|down|docker-restart|docker-logs|docker-ps):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Data and housekeeping:"
	@grep -E '^(refresh|clean|distclean):.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "    \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

## ----------------------------------------------------- local development ----

setup: $(VENV)/.installed ## Create .venv and install pinned dependencies

$(VENV)/.installed: requirements.txt
	@echo "==> Creating virtual environment in $(VENV)"
	@python3 -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pip
	@echo "==> Installing pinned dependencies"
	@$(PIP) install --quiet -r requirements.txt
	@touch $@
	@echo "==> Environment ready. Python: $$($(PY) -V)"

seed: $(DB) ## Build app/gbd.db from the seed CSVs (skipped if up to date)

$(DB): $(VENV)/.installed etl/load_seed.py data/gbd_seed.csv data/gbd_ranked_seed.csv
	@echo "==> Seeding database"
	@$(PY) etl/load_seed.py

reseed: setup ## Rebuild the database from scratch
	@rm -f $(DB)
	@$(MAKE) --no-print-directory seed

run: $(DB) ## Start the app (dashboard + API) in the background
	@$(MAKE) --no-print-directory stop
	@mkdir -p $(RUN_DIR)
	@echo "==> Starting app on :$(PORT)"
	@nohup $(UVICORN) app.main:app --host 127.0.0.1 --port $(PORT) \
		> $(RUN_DIR)/app.log 2>&1 & echo $$! > $(RUN_DIR)/app.pid
	@$(MAKE) --no-print-directory wait-api \
		|| { echo "!! App did not come up -- see $(RUN_DIR)/app.log"; exit 1; }
	@echo ""
	@echo "    Dashboard  $(APP_URL)"
	@echo "    API        $(API_URL)/api      (docs at $(API_URL)/docs)"
	@echo ""
	@echo "    make logs    follow output      make stop    shut down"
	@echo ""

stop: ## Stop the local app
	@if [ -f $(RUN_DIR)/app.pid ]; then \
		pid=$$(cat $(RUN_DIR)/app.pid); \
		if kill $$pid 2>/dev/null; then echo "==> Stopped app (pid $$pid)"; fi; \
		rm -f $(RUN_DIR)/app.pid; \
	fi

restart: stop run ## Restart the local servers

status: ## Show what is listening on :8000
	@echo "==> Listeners"
	@lsof -nP -iTCP:$(PORT) -sTCP:LISTEN 2>/dev/null || echo "    (none)"
	@echo "==> Containers"
	@docker compose ps 2>/dev/null || echo "    (docker unavailable)"

smoke: ## Check that every API endpoint answers
	@echo "==> Smoke testing $(API_URL)"
	@for path in \
		"/api/health" \
		"/api/meta" \
		"/api/indicators" \
		"/api/trend?indicator=tobacco_sev" \
		"/api/ranked?type=causes" \
		"/api/export.csv?indicator=le" ; do \
		code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$(API_URL)$$path"); \
		if [ "$$code" = "200" ]; then echo "    ok   $$code  $$path"; \
		else echo "    FAIL $$code  $$path"; fail=1; fi; \
	done; \
	code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$(APP_URL)/"); \
	if [ "$$code" = "200" ]; then echo "    ok   $$code  /  (dashboard)"; \
	else echo "    FAIL $$code  /  (dashboard)"; fail=1; fi; \
	[ -z "$$fail" ] || exit 1

open: ## Open the dashboard in a browser
	@open $(APP_URL) 2>/dev/null || echo "Open $(APP_URL)"

logs: ## Follow the local API log
	@tail -f $(RUN_DIR)/app.log

## ------------------------------------------------------------- docker ----

up: ## Build and start the container
	@docker compose up -d --build
	@$(MAKE) --no-print-directory wait-api \
		|| { echo "!! API did not come up -- try: make docker-logs"; exit 1; }
	@echo ""
	@echo "    Dashboard  $(APP_URL)"
	@echo "    API        $(API_URL)/api"
	@echo ""

down: ## Stop and remove the container (frees the port)
	@docker compose down

docker-restart: down up ## Rebuild and restart the container

docker-logs: ## Follow the container log
	@docker compose logs -f

docker-ps: ## Show container status
	@docker compose ps

## --------------------------------------------------- data and cleanup ----

refresh: setup ## Ingest the newest GBD export from data/incoming/
	@./refresh.sh

clean: ## Remove the database, logs, and caches (keeps the venv)
	@rm -rf $(RUN_DIR) $(DB)
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "==> Cleaned. Rebuild the database with: make seed"

distclean: clean ## Also remove the virtual environment
	@rm -rf $(VENV)
	@echo "==> Removed $(VENV). Recreate it with: make setup"
