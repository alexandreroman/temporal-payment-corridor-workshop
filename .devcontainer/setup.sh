#!/usr/bin/env bash
#
# One-time Codespace provisioning (devcontainer onCreateCommand).
#
# Installs everything the guide's local prerequisites list would otherwise
# ask a learner to install by hand — make, jq, uv (which also provisions
# Python 3.13), and the Temporal CLI — then syncs dependencies and seeds a
# working dev `.env`. It is idempotent: safe to re-run without clobbering an
# existing checkout.
set -euo pipefail

# The uv and Temporal CLI installers drop binaries here. Add both to PATH up
# front so the later steps in THIS script can call `uv` and `temporal`; the
# devcontainer's remoteEnv makes the same paths available to the interactive
# shell and VS Code tasks afterwards.
export PATH="$HOME/.local/bin:$HOME/.temporalio/bin:$PATH"

# The base Ubuntu image ships neither make (runs every guide command) nor jq
# (used by `make capture-history`, guide step 12).
sudo apt-get update
sudo apt-get install -y --no-install-recommends make jq

# uv manages Python and project dependencies. It also downloads the Python
# version pinned in .python-version (3.13), so no system Python is required.
# Source: https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

# The Temporal CLI (`temporal`). The guide runs `temporal workflow ...` from
# the host from step 03 on, and `make capture-history` uses it too.
# Source: https://docs.temporal.io/cli#install
curl -sSf https://temporal.download/cli.sh | sh

# Install project dependencies (and the pinned Python) into .venv.
uv sync

# Enable the ruff pre-commit git hook (mirrors the local setup step).
make setup

# Seed a working dev `.env` without overwriting one that already exists (-n).
# Every value in .env.example has a working dev default, so the stack runs
# out of the box; a learner only adds a provider key for LLM scenarios.
cp -n .env.example .env

# Workshop folder paths are long, so a default single-line prompt pushes the
# typed command far to the right and wraps awkwardly. Put the current directory
# name on its own line and drop to a bare `$ ` prompt beneath it, keeping
# commands easy to read. The PCW_PROMPT marker keeps this idempotent: `grep -qs`
# tolerates a missing ~/.bashrc (never aborts under `set -e`) and skips the
# append on re-runs so the block is never added twice.
if ! grep -qs 'PCW_PROMPT' "$HOME/.bashrc"; then
	cat >>"$HOME/.bashrc" <<'EOF'

# PCW_PROMPT: current directory name on its own line, bare `$ ` prompt beneath (long workshop paths).
PS1='\[\e[1;34m\]\W\[\e[0m\]\n\$ '
EOF
fi
