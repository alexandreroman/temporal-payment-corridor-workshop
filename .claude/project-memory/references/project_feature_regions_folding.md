---
name: "Feature blocks use VS Code folding regions"
description: "FEATURE markers are # region / # endregion so VS Code auto-folds dormant features; learners see a decluttered base app"
type: project
---

# Feature blocks use VS Code folding regions

Workshop feature markers are VS Code folding regions —
`# region FEATURE-ON: <name>` / `# endregion FEATURE-ON: <name>`
(and the `FEATURE-OFF` inverse for the live base code) — not the
former `# --- FEATURE: <name> ---` delimiters. Both kinds are
regions, but they fold differently on open: `.vscode/settings.json`
carries two `[python]` `explicitFolding.rules` — `FEATURE-ON:`
regions `autoFold: true` (collapsed), `FEATURE-OFF:` regions
`autoFold: false` (expanded) — plus a global
`explicitFolding.autoFold: "none"` (required, else the extension
auto-folds every region it detects, including `FEATURE-OFF`). So
the dormant feature alternatives collapse while the live base code
(`FEATURE-OFF`) stays visible; both remain foldable manually.
`.vscode/extensions.json` recommends `zokugun.explicit-folding`.

**Why:** the pedagogical goal is that a learner reads the code
without being polluted by every dormant feature. Folding the
regions on open shows a clean base app plus a named list of
available features; the learner activates one via the CLI
(`make feature-enable NAME=<name>`) and expands that region to
study it.

**How to apply:**
- The CLI toggles *file text* (comment/uncomment); it cannot
  drive VS Code fold state. Enabling a feature does NOT auto-expand
  its region — the learner expands it manually. This is by design
  ("fold by default, manual expand"); do not try to make the CLI
  unfold regions.
- The `region` keyword is fixed by the language config, not a
  settings key, so the marker itself must carry `region` /
  `endregion` for VS Code to fold it.
- Marker grammar is VS Code-only pedagogy; the toggle mechanics
  and body-authoring rules are unchanged — see
  [[reference_feature_block_authoring.md]].
- The external workshop guide references the marker syntax; it
  lives outside this repo and must be updated there separately.
