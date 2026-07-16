---
name: "Import symbols from their canonical public module"
description: "Import pydantic_data_converter from temporalio.contrib.pydantic, not the pydantic_ai re-export, to avoid Pylance reportPrivateImportUsage."
type: feedback
---

# Import symbols from their canonical public module

Import shared symbols from the module that actually defines and
publicly exports them, not from another package that merely
re-exports them. Concretely: import `pydantic_data_converter` from
`temporalio.contrib.pydantic`, not from
`pydantic_ai.durable_exec.temporal`.

**Why:** `pydantic_ai.durable_exec.temporal` re-exports
`pydantic_data_converter` (same object, verified with `a is b`) but
does not list it in its public API, so Pylance raises
`reportPrivateImportUsage`. Sourcing from the canonical module
silences the warning and avoids depending on a re-export that could
disappear in a future release.

**How to apply:** when a type checker flags a private/unexported
import, trace the symbol to its defining module and import from there;
keep the third-party import group alphabetically sorted.
