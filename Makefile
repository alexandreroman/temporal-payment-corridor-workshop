# Developer task runner. Run `make` (or `make help`) to list the targets.
#
# Two ways to run the stack:
#   * `make dev`    — Temporal in a container; payments + web UI on the host
#                     with hot reload (fast inner loop).
#   * `make app-up` — the full stack (Temporal + payments + web UI) in
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
WEBUI_PORT            := $(shell sed -nE 's/.*"([0-9]+):8000".*/\1/p' compose.override.yaml | head -n1)
TEMPORAL_UI_PORT      := $(shell sed -nE 's/.*"([0-9]+):8233".*/\1/p' compose.override.yaml | head -n1)
TEMPORAL_GRPC_PORT    := $(shell sed -nE 's/.*"([0-9]+):7233".*/\1/p' compose.override.yaml | head -n1)
PAYMENTS_METRICS_PORT := $(shell sed -nE 's/.*"([0-9]+):9464".*/\1/p' compose.override.yaml | head -n1)
MEMORY_PORT           := $(shell sed -nE 's/.*"([0-9]+):8010".*/\1/p' compose.override.yaml | head -n1)
# Point the host-side dev flow (uv run payments/webui) at the remapped ports.
# Assign unconditionally (:=, not ?=): the override file is the source of truth
# for published ports, so these must beat the .env baseline already exported
# above. Plain := (not `override`) still lets an explicit `make VAR=...` win.
TEMPORAL_ADDRESS      := localhost:$(TEMPORAL_GRPC_PORT)
PAYMENTS_METRICS_HOST := 0.0.0.0
export TEMPORAL_ADDRESS WEBUI_PORT PAYMENTS_METRICS_HOST PAYMENTS_METRICS_PORT MEMORY_PORT
else
# Without an override the published ports equal the conventional defaults.
# Use ?= for ports that have a matching app env var so a value set in .env
# still wins over the hard-coded default (TEMPORAL_UI_PORT has no app var).
WEBUI_PORT            ?= 8000
TEMPORAL_UI_PORT      := 8233
PAYMENTS_METRICS_PORT ?= 9464
MEMORY_PORT           ?= 8010
endif

# Banner listing where to reach the running components.
define show_urls
	@echo ""
	@echo "The stack is up. Open:"
	@echo "  Web UI              http://localhost:$(WEBUI_PORT)"
	@echo "  Corridor memory     http://localhost:$(MEMORY_PORT)"
	@echo "  Temporal Web UI     http://localhost:$(TEMPORAL_UI_PORT)  (via gateway)"
	@echo "  Payments metrics    http://localhost:$(PAYMENTS_METRICS_PORT)/metrics"
endef

##@ Setup

.PHONY: setup
setup: ## Enable the local ruff pre-commit hook (run once after cloning)
	git config core.hooksPath .githooks
	@echo "Git hooks enabled: ruff runs before every commit (.githooks)."

##@ Infra

.PHONY: infra-up
infra-up: ## Bring up temporal + codec + gateway (gateway is the Web UI entry point)
	docker compose up -d temporal codec gateway

.PHONY: infra-down
infra-down: ## Stop the Temporal dev server (keeps container around)
	docker compose stop temporal

.PHONY: infra-logs
infra-logs: ## Follow logs from the Temporal dev server
	docker compose logs -f temporal

##@ App (host, hot reload)

.PHONY: payments
payments: ## Run the payments worker on the host with hot reload
	uv run payments

.PHONY: simulator
simulator: ## Simulate a payment anomaly (SCENARIO=<name>; see `uv run simulator --list-scenarios`)
	uv run simulator $(if $(SCENARIO),--scenario $(SCENARIO))

.PHONY: webui
webui: ## Run the web UI on the host with hot reload
	uv run webui

.PHONY: memory
memory: ## Run the corridor memory service on the host with hot reload
	uv run memory

.PHONY: dev
dev: .venv infra-up ## Start Temporal, then run payments + web UI on the host with hot reload
	$(show_urls)
	@$(MAKE) -j payments webui memory

.venv: pyproject.toml uv.lock
	uv sync
	@touch .venv

##@ Stack (containers)

.PHONY: app-up
app-up: ## Bring up the full stack in containers (temporal + payments + web UI)
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

# NOTE: the override also replaces temporal's `command` so --ui-codec-endpoint
# points at the gateway's REMAPPED host port (CASPER_PORT), not the hard-coded
# 8233 in compose.yaml — otherwise the Web UI, served from CASPER_PORT, would
# look for the codec on 8233 and decoding would break in a worktree. This
# mirrors compose.yaml's temporal command, so keep the two in sync.
.PHONY: worktree-ports
worktree-ports: ## Remap host ports off CASPER_PORT so parallel worktrees don't collide
	@if [ -n "$$CASPER_PORT" ]; then \
		printf 'services:\n  temporal:\n    ports: !override\n      - "%s:7233"\n    command: !override\n      - server\n      - start-dev\n      - --ip\n      - 0.0.0.0\n      - --ui-codec-endpoint\n      - http://localhost:%s/codec\n      - --namespace\n      - payments\n      - --namespace\n      - memory\n  gateway:\n    ports: !override\n      - "%s:8233"\n  payments:\n    ports: !override\n      - "%s:9464"\n  webui:\n    ports: !override\n      - "%s:8000"\n  memory:\n    ports: !override\n      - "%s:8010"\n' \
			$$((CASPER_PORT + 1)) "$$CASPER_PORT" "$$CASPER_PORT" $$((CASPER_PORT + 2)) $$((CASPER_PORT + 3)) $$((CASPER_PORT + 4)) > compose.override.yaml; \
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

##@ Gateway & codec

.PHONY: gateway
gateway: ## (Re)start the API gateway — single entry point (Web UI + /codec) at http://localhost:8233
	docker compose up -d gateway

.PHONY: capture-history
capture-history: ## Regenerate payments/testdata/coordinator-history.json for the replay test (needs `make memory` running)
	uv run python -m tools.capture_history

##@ Helpers

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(firstword $(MAKEFILE_LIST))
