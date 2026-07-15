# Developer task runner. Run `make` (or `make help`) to list the targets.
#
# Infra (the Temporal dev server) runs in a container via `make infra-up`;
# the worker and simulator run on the host via uv. `make dev` ties it together.

.DEFAULT_GOAL := dev

# Canonical environment. Required for app targets, baseline for dev.
# Optional: a missing .env is not an error.
ifneq (,$(wildcard .env))
include .env
export
endif

# Banner listing where to reach the running components.
define show_urls
	@echo ""
	@echo "The stack is up. Open:"
	@echo "  Temporal dashboard http://localhost:8233"
	@echo "  Worker metrics     http://localhost:9464/metrics"
endef

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

##@ App

.PHONY: worker
worker: ## Run the Temporal worker on the host with hot reload
	uv run worker

.PHONY: simulator
simulator: ## Simulate an incoming payment anomaly
	uv run simulator

.PHONY: dev
dev: .venv infra-up ## Start Temporal, then run the worker on the host with hot reload
	$(show_urls)
	@$(MAKE) worker

.venv: pyproject.toml uv.lock
	uv sync
	@touch .venv

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

##@ Helpers

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(firstword $(MAKEFILE_LIST))
