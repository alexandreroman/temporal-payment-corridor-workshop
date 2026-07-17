# Developer task runner. Run `make` (or `make help`) to list the targets.
#
# Two ways to run the stack:
#   * `make dev`    — Temporal in a container; payments worker + API and
#                     memory service on the host with hot reload (fast inner
#                     loop). The web UI is served by the gateway from a
#                     volume mount, so editing its files needs only a
#                     browser refresh, no restart.
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
GATEWAY_PORT          := $(shell sed -nE 's/.*"([0-9]+):8080".*/\1/p' compose.override.yaml | head -n1)
TEMPORAL_GRPC_PORT    := $(shell sed -nE 's/.*"([0-9]+):7233".*/\1/p' compose.override.yaml | head -n1)
MEMORY_PORT           := $(shell sed -nE 's/.*"([0-9]+):8010".*/\1/p' compose.override.yaml | head -n1)
# Metrics and the payments API are no longer published container ports (see
# compose.yaml / worktree-ports), so there is nothing to read back for them.
# In dev they run as HOST processes; derive their ports from the gateway's
# (already worktree-unique) host port with the same offsets worktree-ports uses
# for the published services, so parallel worktrees never collide.
PAYMENTS_METRICS_PORT := $(shell echo $$(($(GATEWAY_PORT) + 2)))
PAYMENTS_API_PORT     := $(shell echo $$(($(GATEWAY_PORT) + 5)))
# Point the host-side dev flow (uv run payments/payments-api) at the remapped
# ports. Assign unconditionally (:=, not ?=): the override file is the source
# of truth for published ports, so these must beat the .env baseline exported
# above. Plain := (not `override`) still lets an explicit `make VAR=...` win.
TEMPORAL_ADDRESS      := localhost:$(TEMPORAL_GRPC_PORT)
PAYMENTS_METRICS_HOST := 0.0.0.0
# The simulator reaches the payments API through the gateway.
GATEWAY_HOST          := localhost
export TEMPORAL_ADDRESS PAYMENTS_METRICS_HOST PAYMENTS_METRICS_PORT MEMORY_PORT PAYMENTS_API_PORT GATEWAY_HOST GATEWAY_PORT
else
# Without an override the published ports equal the conventional defaults.
# Use ?= for ports that have a matching app env var so a value set in .env
# still wins over the hard-coded default (GATEWAY_PORT has no app-side default
# other than this; the gateway container always listens on 8080 internally).
GATEWAY_PORT          := 8080
PAYMENTS_METRICS_PORT ?= 9464
MEMORY_PORT           ?= 8010
PAYMENTS_API_PORT     ?= 8020
GATEWAY_HOST          := localhost
export PAYMENTS_API_PORT GATEWAY_HOST GATEWAY_PORT
endif

# Banner listing where to reach the running components. Only the two
# user-facing surfaces are shown: the Web UI and the Temporal Web UI, both
# reached through the gateway (respectively `/` and `/temporal`). The memory
# service, payments API, and metrics endpoints are intentionally not
# advertised — the gateway is the single entry point (see gateway/Caddyfile).
define show_urls
	@echo ""
	@echo "The stack is up. Open:"
	@echo "  Web UI            http://localhost:$(GATEWAY_PORT)"
	@echo "  Temporal Web UI   http://localhost:$(GATEWAY_PORT)/temporal"
endef

##@ Setup

.PHONY: setup
setup: ## Enable the local ruff pre-commit hook (run once after cloning)
	git config core.hooksPath .githooks
	@echo "Git hooks enabled: ruff runs before every commit (.githooks)."

##@ Infra

# Dev-mode compose file set. compose.dev.yaml points the containerised gateway
# at the HOST payments API (host.docker.internal) for the hot-reload flow; it is
# NOT auto-merged (only compose.override.yaml is), so it must be passed
# explicitly. The per-worktree compose.override.yaml (remapped ports) is
# included only when present — a plain checkout has none.
COMPOSE_DEV_FILES := -f compose.yaml $(if $(wildcard compose.override.yaml),-f compose.override.yaml,) -f compose.dev.yaml

.PHONY: infra-up
infra-up: ## Bring up temporal + codec + gateway (gateway is the Web UI entry point)
	docker compose $(COMPOSE_DEV_FILES) up -d temporal codec gateway

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

.PHONY: payments-api
payments-api: ## Run the payments HTTP API on the host with hot reload
	uv run payments-api

.PHONY: simulator
simulator: ## Simulate a payment anomaly (SCENARIO=<name>; see `make simulator-list`)
	uv run simulator $(if $(SCENARIO),--scenario $(SCENARIO))

.PHONY: simulator-list
simulator-list: ## List the available payment-anomaly scenarios
	uv run simulator --list-scenarios

.PHONY: memory
memory: ## Run the corridor memory service on the host with hot reload
	uv run memory

.PHONY: dev
dev: .venv infra-up ## Start Temporal, then run payments worker + API and memory on the host (hot reload)
	$(show_urls)
	@$(MAKE) -j payments payments-api memory

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
# mirrors compose.yaml's temporal command, so keep the two in sync (including
# --ui-public-path, which must stay /temporal here too).
#
# webui has no ports entry to remap: it is reached only through the gateway
# (see gateway/Caddyfile), never published directly. Its per-worktree port
# (CASPER_PORT+3, unused by any other service below) is derived straight from
# CASPER_PORT in the Makefile's WEBUI_PORT instead — see the ifneq block above.
.PHONY: worktree-ports
worktree-ports: ## Remap host ports off CASPER_PORT so parallel worktrees don't collide
	@if [ -n "$$CASPER_PORT" ]; then \
		printf 'services:\n  temporal:\n    ports: !override\n      - "%s:7233"\n    command: !override\n      - server\n      - start-dev\n      - --ip\n      - 0.0.0.0\n      - --ui-codec-endpoint\n      - http://localhost:%s/codec\n      - --ui-public-path\n      - /temporal\n      - --namespace\n      - payments\n      - --namespace\n      - memory\n      - --search-attribute\n      - corridor=Keyword\n      - --search-attribute\n      - anomalyType=Keyword\n      - --search-attribute\n      - status=Keyword\n  gateway:\n    ports: !override\n      - "%s:8233"\n  payments:\n    ports: !override\n      - "%s:9464"\n  payments-api:\n    ports: !override\n      - "%s:8020"\n  memory:\n    ports: !override\n      - "%s:8010"\n' \
			$$((CASPER_PORT + 1)) "$$CASPER_PORT" "$$CASPER_PORT" $$((CASPER_PORT + 2)) $$((CASPER_PORT + 5)) $$((CASPER_PORT + 4)) > compose.override.yaml; \
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
gateway: ## (Re)start the API gateway — single entry point (Web UI + /codec) at http://localhost:8080
	docker compose up -d gateway

.PHONY: capture-history
capture-history: ## Capture coordinator-history.json from a completed memory-hit run (WORKFLOW_ID=correction-pmt-XXXX)
	@test -n "$(WORKFLOW_ID)" || { echo "Usage: make capture-history WORKFLOW_ID=correction-pmt-XXXX"; exit 2; }
	temporal workflow show \
		--address $(TEMPORAL_ADDRESS) --namespace payments \
		--workflow-id $(WORKFLOW_ID) -o json \
	| jq --arg wf "$(WORKFLOW_ID)" '{workflow_id: $$wf, history: .}' \
	> payments/testdata/coordinator-history.json

##@ Helpers

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(firstword $(MAKEFILE_LIST))
