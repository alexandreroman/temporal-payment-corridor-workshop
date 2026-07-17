# Project Memory

> When a new decision **contradicts** an existing
> memory note, do NOT silently override it.
> Instead: surface the conflict, quote the
> existing memory, explain how the new decision
> differs, and ask for explicit confirmation
> before updating. **Do NOT take any action** —
> no tool calls, no file writes — until confirmed.

- [Dev workflow: hot reload and HTML preview](references/feedback_dev_workflow.md) — use `make dev` for the hot-reload stack; preview HTML via Casper Browser when available.
- [Casper worktree port remap](references/project_casper_port_remap.md) — gateway + temporal gRPC honor CASPER_PORT via compose.override.yaml; run the simulator through make (bare uv run uses localhost:7233 and fails).
- [Gateway payments-API upstream is mode-specific](references/project_gateway_payments_upstream.md) — container mode uses in-network payments-api:8020; dev mode uses host.docker.internal via dev-only compose.dev.yaml, never the auto-merged override.
- [Docker images run modules from source](references/project_docker_build.md) — images install deps only and run `python -m payments.main_worker`/`memory.main`/`codec.main`; never build the wheel (readme field breaks the build).
- [Module layout: packages per domain with thin main.py](references/project_module_layout.md) — package-per-domain, thin main.py + isolated definition; webui/ is now static assets served by the gateway, no Python module.
- [Config conventions: host/port env pairs and local-only Logfire](references/project_config_conventions.md) — endpoints use split `*_HOST`+`*_PORT` env vars; Logfire runs local-only (`send_to_logfire=False`, no token).
- [Generated text and code must be in English](references/feedback_english_only.md) — all output (code, comments, docs, commits, prose) is written in English, whatever the conversation language.
- [Never reference company names](references/feedback_no_company_names.md) — no company/organization name may appear in code, docs, commits, memory, or prose; refer generically.
- [Workshop content must be timeless](references/feedback_timeless_content.md) — no dates, times, headcounts, locations, or scheduling in any artifact; keep material reusable and undated.
- [Code must be abundantly commented, with sources](references/feedback_code_comments.md) — thorough comments explaining important/production choices, each with a source link; the code is the teaching surface.
- [Docs and comments stay focused on Temporal](references/feedback_docs_temporal_focus.md) — strip app-implementation plumbing (routing, binds, listing seams, config-load asides) from README/guide/comments; keep Temporal teaching, sources, and NOTE: markers.
- [NOTE: marker flags learner-attention comments](references/feedback_note_marker.md) — single literal `NOTE:` prefix marks the non-obvious comments a learner should study; baseline + FEATURE prose.
- [search-attributes is tagging-only](references/project_search_attributes_scope.md) — SA only upserts attributes in the workflow; never rewires the API/Web UI listing, so the payment context always survives.
- [search-attributes status lifecycle is terminal-valued](references/project_search_attributes_status_lifecycle.md) — coordinator publishes a terminal status ("applied"/"held") before every return; SA-enabled tests must register all three keys.
- [Git commit messages: imperative verb-first](references/feedback_git_commit_style.md) — capitalized imperative verb ≤50 chars, no prefix at all (no conventional-commit types, no scope prefixes like `webui:`); why in body at 72 cols.
- [Default to subagent-driven implementation](references/feedback_subagent_driven_default.md) — execute approved plans with subagent-driven development by default; source edits via skillbox:code-writer.
- [Design specs are intentionally not version-controlled](references/reference_specs_local_only.md) — `docs/` is gitignored on purpose; specs stay local, their absence from git is normal.
- [Workshop audience and scope](references/project_workshop_audience.md) — Python-strong audience who completed Temporal 101 and 102, in cross-border payments; format 3×2h hands-on; emphasis: durable agents, encryption, light metrics, search attributes, tests.
- [Transfer domain model is intentionally simplified](references/project_domain_model_simplified.md) — each anomaly targets one field; seeded pattern is US->IN/WRONG_BIC→HDFCINBBXXX (India uses SWIFT/BIC, not IBAN); README documents the simplification.
- [Regenerating the replay fixture via the temporal CLI](references/reference_capture_history_cli.md) — make capture-history WORKFLOW_ID=... captures a completed memory-hit run via `temporal workflow show -o json` + jq; no standalone memory service.
- [Testing TemporalAgent-based workflows under start_local](references/reference_temporal_agent_testing.md) — Agent.override(model=...) doesn't reach the model activity; register a TestModel stand-in under the real workflow name instead. Fernet import needs imports_passed_through() too.
- [Authoring toggleable FEATURE blocks](references/reference_feature_block_authoring.md) — single-# code vs double-# prose; pair REPLACE features with FEATURE-OFF; commented body must match ruff output; verify enable→parse→disable round-trip.
- [Feature blocks use VS Code folding regions](references/project_feature_regions_folding.md) — markers are `# region FEATURE-ON:`/`FEATURE-OFF:`; FEATURE-ON auto-folds on open, FEATURE-OFF stays expanded (explicit-folding); CLI toggles text, learner expands manually.
- [Import symbols from their canonical public module](references/feedback_canonical_imports.md) — import pydantic_data_converter from temporalio.contrib.pydantic, not the pydantic_ai re-export, to avoid Pylance reportPrivateImportUsage.
- [Payments component naming vs Temporal Worker primitive](references/project_payments_component_naming.md) — prose calls the deployable component "payments"; `Worker`/`worker` stays reserved for the Temporal SDK primitive and its identifiers.
- [retry-alerting metric tags](references/reference_retry_alert_metric_tags.md) — corridor_correction_retries_alerted is tagged field/source (proposal has no corridor/anomaly type), matching sibling corridor_* metrics.
- [Memory entries are present-tense standing facts](references/feedback_memory_present_tense.md) — phrase every entry as a current fact; never narrate past events ("renamed from", "the user asked").
- [codec package is a support tool, not a FEATURE surface](references/feedback_codec_server_not_a_feature.md) — codec-server behavior (e.g. bearer-token auth) is plain always-on code; FEATURE blocks belong only in app components; features.py ROOTS excludes codec.
- [Gateway is the single HTTP entry point; codec is always-on infra](references/project_gateway_topology.md) — Caddy on :8080 serves the static Web UI at `/` (no webui process) and routes `/temporal`, `/api/payments/v1`, `/codec`→codec (non-profiled service, `restart: unless-stopped`); same-origin, no CORS; codec warns and falls back to insecure defaults (token `changeme`) when unset; key is CODEC_ENCRYPTION_KEY.
- [Testing the memory service across the FEATURE toggle](references/reference_memory_service_testing.md) — HTTP tests need a store-backed client stub to pass both toggle states; MemoryWorkflow tests run unsandboxed; state is seeded in @workflow.init (no barrier query).
- [Run the temporal CLI from the host, never a container](references/feedback_temporal_cli_from_host.md) — CLI is always host-side; localhost:<port>/codec reaches the gateway only from the host, not a container's loopback.
- [Gateway (Caddy) healthcheck reports unhealthy by design](references/reference_gateway_healthcheck_unhealthy.md) — the gateway probe hits the unavailable Caddy admin API; ignore its Health column, Caddy still serves the Web UI and /codec.
- [Enforced format is ruff defaults (88 cols)](references/feedback_ruff_line_length.md) — no ruff config, so line length is 88 (not CLAUDE.md's 120); a pre-commit hook lints the whole tree, so every commit needs the entire repo clean.
- [Implementation status](references/project_implementation_status.md) — reusable scaffold tracking pending workshop feature-set work; currently nothing pending.
- [Memory service publishes no host port](references/reference_memory_port_unpublished.md) — memory is `expose`d only (memory:8010 in-network); MEMORY_PORT for dev is derived from GATEWAY_PORT+4, not read from the override.
- [All-features test suite is green except the intentional replay failure](references/project_all_features_test_contract.md) — with every feature on, only test_replay fails (by design, guide/12); all other tests hold in baseline, single-feature, and all-features states.
