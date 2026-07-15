"""Client script: simulate an incoming payment anomaly.

Starts a ``PaymentCorrectionCoordinator`` execution and prints the outcome.
The default anomaly matches a pre-seeded corridor-memory pattern, so it is
corrected end-to-end without any LLM call (no API key required).

Run with:  ``uv run simulator``  (worker and dev server must be running).
"""

from __future__ import annotations

import asyncio
import os
import uuid

from dotenv import load_dotenv
from temporalio.client import Client

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

# --- FEATURE: payload-encryption ---
# from shared.encryption import EncryptionCodec, build_data_converter, load_key
#
# --- END FEATURE: payload-encryption ---
from shared.models import AnomalyType, PaymentAnomaly
from worker.workflows import TASK_QUEUE, PaymentCorrectionCoordinator

# Configuration from environment / local .env (see .env.example).
load_dotenv()

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")


async def main() -> None:
    # --- FEATURE-DEFAULT: payload-encryption ---
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        # Same data converter as the worker, so Pydantic models round-trip.
        plugins=[PydanticAIPlugin()],
    )
    # --- END FEATURE-DEFAULT: payload-encryption ---
    # --- FEATURE: payload-encryption ---
    # # Encrypt payloads across the Temporal boundary, matching the worker's
    # # data converter. PydanticAIPlugin only installs its own data converter
    # # when the caller doesn't pass one, so keeping the plugin alongside an
    # # explicit data_converter is safe — verified empirically: dropping
    # # PydanticAIPlugin instead breaks TemporalAgent workflow sandbox
    # # validation at worker start-up. Source:
    # # https://docs.temporal.io/production-deployment/data-encryption
    # key = load_key()
    # assert key, "set CORRIDOR_ENCRYPTION_KEY to enable payload encryption"
    # client = await Client.connect(
    #     TEMPORAL_ADDRESS,
    #     data_converter=build_data_converter(EncryptionCodec(key)),
    #     plugins=[PydanticAIPlugin()],
    # )
    # --- END FEATURE: payload-encryption ---

    anomaly = PaymentAnomaly(
        payment_id=f"pmt-{uuid.uuid4().hex[:8]}",
        corridor="US->IN",
        amount=15000.0,
        currency="USD",
        anomaly_type=AnomalyType.WRONG_IBAN,
        details={"beneficiary": "Acme Textiles Pvt Ltd", "iban": "IN00INVALID"},
    )

    outcome = await client.execute_workflow(
        PaymentCorrectionCoordinator.run,
        anomaly,
        id=f"correction-{anomaly.payment_id}",
        task_queue=TASK_QUEUE,
    )

    print(f"applied : {outcome.applied}")
    print(f"message : {outcome.message}")
    if outcome.proposal is not None:
        p = outcome.proposal
        print(
            f"proposal: {p.field_to_fix}={p.proposed_value} "
            f"(confidence {p.confidence:.2f}, via {p.source} / {p.agent_name})"
        )

    # --- FEATURE: human-approval-signal ---
    # When a proposal needs human sign-off, the coordinator waits for a
    # decision. Send it from a second client (or here, after starting the
    # workflow without awaiting its result):
    #
    # from shared.models import ApprovalDecision
    # handle = client.get_workflow_handle("correction-...")
    # await handle.signal(
    #     PaymentCorrectionCoordinator.approve_correction,
    #     ApprovalDecision(approved=True, approver="ops@bank.example"),
    # )
    # --- END FEATURE: human-approval-signal ---


def cli() -> None:
    """Console-script entry point (`uv run simulator`)."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
