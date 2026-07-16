"""Worker definition: build the Temporal ``Worker`` for the payment corridor.

Keeps the object construction — task queue, workflow and activity
registration — separate from the runtime/observability bootstrap in
``worker/main.py``. Importing this module triggers the workflow import
chain (``worker.workflows`` -> ``worker.agents``), and ``agents`` reads
environment variables at import time, so callers must ``load_dotenv()``
before importing it.
"""

from __future__ import annotations

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities import apply_correction

# --- FEATURE: settlement-confirmation ---
# from worker.activities import confirm_settlement
# --- END FEATURE: settlement-confirmation ---

from worker.memory import (
    CorridorMemoryWorkflow,
    read_corridor_memory,
    write_corridor_memory,
)
from worker.workflows import (
    TASK_QUEUE,
    ComplianceAgentWorkflow,
    InstructionAgentWorkflow,
    PaymentCorrectionCoordinator,
)


def build_worker(client: Client) -> Worker:
    """Construct the payment-corridor worker for the given client.

    Registers every workflow and activity on the shared task queue. The
    Pydantic AI agents' own activities are auto-registered by the
    ``PydanticAIPlugin`` installed on the client.
    """
    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            PaymentCorrectionCoordinator,
            InstructionAgentWorkflow,
            ComplianceAgentWorkflow,
            CorridorMemoryWorkflow,
        ],
        activities=[
            read_corridor_memory,
            write_corridor_memory,
            apply_correction,
            # --- FEATURE: settlement-confirmation ---
            # confirm_settlement,
            # --- END FEATURE: settlement-confirmation ---
        ],
    )
