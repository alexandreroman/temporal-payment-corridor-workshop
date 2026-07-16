---
name: "codec package is a support tool, not a FEATURE surface"
description: "Codec-server behavior is plain always-on code; toggleable FEATURE blocks belong only in the app components"
type: feedback
---

# codec package is a support tool, not a FEATURE surface

The `codec/` package (the remote codec server) is a
standalone support tool for the Temporal Web UI, **not**
part of the workshop's
progressive-activation FEATURE mechanism. Behavior there —
including the bearer-token authentication that gates every
request — ships as plain, always-on default code with **no**
`# region FEATURE-ON/OFF:` markers. When `CODEC_SERVER_AUTH_TOKEN`
(or `CODEC_ENCRYPTION_KEY`) is unset the server logs a WARNING and
falls back to an insecure built-in demo default (token `changeme`)
rather than failing fast, so it always starts.
Toggleable FEATURE blocks live only in the app components
(`payments/`, `simulator/`, `webui/`, `shared/`, `memory/`),
which is why `tools/features.py` `ROOTS` deliberately excludes
`codec`.

**Why:** the codec server is auxiliary infrastructure a
learner runs to decrypt payloads in the UI — there is no
pedagogical "toggle" to activate there, and nothing in the
repo calls it (only the external Temporal Web UI does), so a
feature block in that package is meaningless.

**How to apply:** when adding codec-server capabilities,
write plain live code; do not wrap it in FEATURE regions and
do not add `codec` to `tools/features.py` `ROOTS`.
Reserve FEATURE blocks for the app components. See
[[project_feature_regions_folding.md]] and
[[reference_feature_block_authoring.md]].
