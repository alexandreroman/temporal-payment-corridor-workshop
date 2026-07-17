"""HTTP client to the corridor-memory service, exposed as two activities.

The passive corridor memory now lives behind its own HTTP service (see the
``memory/`` package). This module holds the two activities the agents use to
talk to it:

  * ``read_corridor_memory`` — look up a known correction pattern, and
  * ``write_corridor_memory`` — remember a newly learned one.

Both are plain Temporal activities that make an outbound HTTP call. The
service's storage backend (in-memory today, durable later) is opaque here:
this module only depends on the stable ``/api/memory/v1`` contract.
"""

from __future__ import annotations

import os

import httpx
from temporalio import activity

from shared.models import AnomalyType, CorridorPattern

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Read at import time like the
# other modules do.
MEMORY_HOST = os.getenv("MEMORY_HOST", "0.0.0.0")
MEMORY_PORT = int(os.getenv("MEMORY_PORT", "8010"))

# NOTE: bind-vs-connect. The service *binds* to MEMORY_HOST, which is often
# 0.0.0.0 ("listen on every interface"). A client cannot *connect* to 0.0.0.0
# on macOS, so we normalize the connect target back to loopback. In containers
# this env var carries a routable address instead — each service gets its own
# MEMORY_HOST (e.g. the Compose service name of the memory container), so
# payments connects to that host rather than to loopback.
_connect_host = "127.0.0.1" if MEMORY_HOST in ("0.0.0.0", "") else MEMORY_HOST
_BASE_URL = f"http://{_connect_host}:{MEMORY_PORT}"


@activity.defn
async def read_corridor_memory(
    corridor: str,
    anomaly_type: AnomalyType,
    beneficiary_bank_id: str | None = None,
) -> CorridorPattern | None:
    """Look up a known correction pattern for a corridor + anomaly type,
    optionally scoped to a beneficiary bank.

    NOTE: The HTTP call lives in an activity precisely because workflow code
    must stay deterministic — all I/O belongs in activities. The memory
    service's storage backend is opaque to this consumer; we only rely on the
    ``/api/memory/v1/lookup`` contract.
    """
    params = {"corridor": corridor, "anomaly_type": anomaly_type.value}
    # NOTE: only send the discriminator when present, so a corridor-wide lookup
    # (bank_id None) issues the exact same request it always has and keys the
    # same way; a bank-specific lookup adds the param without disturbing it.
    if beneficiary_bank_id:
        params["beneficiary_bank_id"] = beneficiary_bank_id

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{_BASE_URL}/api/memory/v1/lookup",
            params=params,
        )
        # Let a 5xx surface as an exception so Temporal retries the activity.
        response.raise_for_status()
        data = response.json()

    # A miss comes back as JSON null (HTTP 200), not an error.
    pattern = CorridorPattern.model_validate(data) if data is not None else None

    meter = activity.metric_meter()
    lookups = meter.create_counter(
        "corridor_memory_lookups", "Passive corridor-memory lookups"
    )
    lookups.add(1, {"corridor": corridor, "result": "hit" if pattern else "miss"})

    if pattern is not None:
        activity.logger.info("Corridor-memory hit for %s/%s", corridor, anomaly_type)
    return pattern


@activity.defn
async def write_corridor_memory(pattern: CorridorPattern) -> None:
    """Remember a newly learned correction pattern."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{_BASE_URL}/api/memory/v1/remember",
            json=pattern.model_dump(mode="json"),
        )
        # Let a 5xx surface as an exception so Temporal retries the activity.
        response.raise_for_status()

    activity.logger.info(
        "Corridor-memory learned pattern for %s/%s",
        pattern.corridor,
        pattern.anomaly_type,
    )
