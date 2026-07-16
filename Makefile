# Developer task runner. Run `make` (or `make help`) to list the targets.
#
# Two ways to run the stack:
#   * `make dev`    — Temporal in a container; worker + web UI on the host
#                     with hot reload (fast inner loop).
#   * `make app-up` — the full stack (Temporal + worker + web UI) in
#                     containers.
#
# CASPER_PORT: when set (Casper workspaces), `make worktree-ports` writes a
# compose.override.yaml that remaps every published host port off CASPER_PORT
# so parallel workspaces never collide.

.DEFAULT_GOAL := dev

# Canonical environment. Required for app targets, baseline for dev.
# Optional: a missing .env is not an error.
ifneq (,$(wildcard .env))
include .env
export
endif

# compose.override.yaml (auto-merged by docker compose) may remap the published
# host ports so parallel workspaces don't collide. It is the source of truth:
# when present, read the actual published ports straight from it so the banner
# and the host-side `make dev` flow can never diverge from what docker binds.
# Otherwise fall back to the conventional defaults.
ifneq (,$(wildcard compose.override.yaml))
WEBUI_URL_PORT     := $(shell sed -nE 's/.*"([0-9]+):8000".*/\1/p' compose.override.yaml | head -n1)
TEMPORAL_UI_PORT   := $(shell sed -nE 's/.*"([0-9]+):8233".*/\1/p' compose.override.yaml | head -n1)
TEMPORAL_GRPC_PORT := $(shell sed -nE 's/.*"([0-9]+):7233".*/\1/p' compose.override.yaml | head -n1)
METRICS_PORT       := $(shell sed -nE 's/.*"([0-9]+):9464".*/\1/p' compose.override.yaml | head -n1)
# Point the host-side dev flow (uv run worker/webui) at the remapped ports.
# Assign unconditionally (:=, not ?=): the override file is the source of truth
# for published ports, so these must beat the .env baseline already exported
# above. Plain := (not `override`) still lets an explicit `make VAR=...` win.
TEMPORAL_ADDRESS     := localhost:$(TEMPORAL_GRPC_PORT)
WEBUI_PORT           := $(WEBUI_URL_PORT)
WORKER_METRICS_HOST  := 0.0.0.0
WORKER_METRICS_PORT  := $(METRICS_PORT)
export TEMPORAL_ADDRESS WEBUI_PORT WORKER_METRICS_HOST WORKER_METRICS_PORT
else
WEBUI_URL_PORT     := 8000
TEMPORAL_UI_PORT   := 8233
METRICS_PORT       := 9464
endif

# Banner listing where to reach the running components.
define show_urls
	@echo ""
	@echo "The stack is up. Open:"
	@echo "  Web UI             http://localhost:$(WEBUI_URL_PORT)"
	@echo "  Temporal dashboard http://localhost:$(TEMPORAL_UI_PORT)"
	@echo "  Worker metrics     http://localhost:$(METRICS_PORT)/metrics"
endef

##@ Setup

.PHONY: setup
setup: ## Enable the local ruff pre-commit hook (run once after cloning)
	git config core.hooksPath .githooks
	@echo "Git hooks enabled: ruff runs before every commit (.githooks)."

##@ Infra

.PHONY: infra-up
infra-up: ## Bring up the Temporal dev server
	docker compose up -d temporal

.PHONY: infra-down
infra-down: ## Stop the Temporal dev server (keeps container around)
	docker compose stop temporal

.PHONY: infra-logs
infra-logs: ## Follow logs from the Temporal dev server
	docker compose logs -f temporal

##@ App (host, hot reload)

.PHONY: worker
worker: ## Run the Temporal worker on the host with hot reload
	uv run worker

.PHONY: simulator
simulator: ## Simulate an incoming payment anomaly
	uv run simulator

.PHONY: webui
webui: ## Run the web UI on the host with hot reload
	uv run webui

.PHONY: dev
dev: .venv infra-up ## Start Temporal, then run worker + web UI on the host with hot reload
	$(show_urls)
	@$(MAKE) -j worker webui

.venv: pyproject.toml uv.lock
	uv sync
	@touch .venv

##@ Stack (containers)

.PHONY: app-up
app-up: ## Bring up the full stack in containers (temporal + worker + web UI)
	docker compose up -d
	$(show_urls)

.PHONY: app-down
app-down: ## Tear down the full stack (removes containers and network)
	docker compose down

.PHONY: app-logs
app-logs: ## Follow logs from every stack container
	docker compose logs -f

##@ Worktree

.PHONY: worktree-init
worktree-init: ## Initialise a worktree: install deps and remap host ports off CASPER_PORT
	uv sync
	@$(MAKE) worktree-ports

.PHONY: worktree-ports
worktree-ports: ## Remap host ports off CASPER_PORT so parallel worktrees don't collide
	@if [ -n "$$CASPER_PORT" ]; then \
		printf 'services:\n  temporal:\n    ports: !override\n      - "%s:7233"\n      - "%s:8233"\n  worker:\n    ports: !override\n      - "%s:9464"\n  webui:\n    ports: !override\n      - "%s:8000"\n' \
			$$((CASPER_PORT + 1)) $$((CASPER_PORT + 2)) $$((CASPER_PORT + 3)) "$$CASPER_PORT" > compose.override.yaml; \
		echo "Wrote compose.override.yaml (CASPER_PORT=$$CASPER_PORT)"; \
	fi

##@ Quality

.PHONY: lint
lint: ## Lint the code
	uv run ruff check .

.PHONY: format
format: ## Format the code
	uv run ruff format .

.PHONY: test
test: ## Run the test suite
	uv run pytest

.PHONY: check
check: lint test ## Run linter and tests

##@ Features (workshop progressive activation)

.PHONY: feature-list
feature-list: ## List workshop features and their state
	uv run python -m tools.features list

.PHONY: feature-status
feature-status: ## Show one feature's regions (NAME=<name>)
	uv run python -m tools.features status $(NAME)

.PHONY: feature-diff
feature-diff: ## Show what enabling a feature changes (NAME=<name>)
	uv run python -m tools.features diff $(NAME)

.PHONY: feature-enable
feature-enable: ## Enable a feature everywhere (NAME=<name>, DRY_RUN=1 to preview)
	uv run python -m tools.features enable $(NAME) $(if $(DRY_RUN),--dry-run,)

.PHONY: feature-disable
feature-disable: ## Disable a feature everywhere (NAME=<name>, DRY_RUN=1 to preview)
	uv run python -m tools.features disable $(NAME) $(if $(DRY_RUN),--dry-run,)

##@ Session 3

.PHONY: codec-server
codec-server: ## Run the codec server for the Temporal UI (decrypts payloads for display)
	uv run python -m codec_server.main

.PHONY: capture-history
capture-history: ## Regenerate worker/testdata/coordinator-history.json for the replay test
	uv run python -m tools.capture_history

##@ Helpers

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(firstword $(MAKEFILE_LIST))
