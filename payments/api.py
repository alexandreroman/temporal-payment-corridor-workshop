"""Payments HTTP API application definition.

The payments component ships as two processes sharing this package: the
Temporal worker (payments/main_worker.py) and this HTTP API. The API holds no
Worker — it is a Temporal *client* that starts corrections, lists in-flight
ones over the Visibility API, and relays human approvals.

Server startup lives in payments/main_api.py; this module defines ``app``,
imported as ``payments.api:app`` by uvicorn. Logfire is configured here (not in
main_api.py) because uvicorn's reload imports this module in a subprocess.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

# region FEATURE-ON: payload-encryption
# from shared.encryption import EncryptionCodec, build_data_converter, load_key
#
# endregion FEATURE-ON: payload-encryption
# NOTE: Load .env before importing payments.workflows: that import chain reaches
# payments.agents, which reads CORRIDOR_MODEL at import time.
load_dotenv()

from payments.workflows import (  # noqa: E402
    TASK_QUEUE,
    PaymentCorrectionCoordinator,
)
from shared.models import (  # noqa: E402
    AnomalyType,
    CorrectionOutcome,
    PaymentAnomaly,
)

# region FEATURE-ON: human-approval-signal
# from shared.models import ApprovalDecision  # noqa: E402
# endregion FEATURE-ON: human-approval-signal

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
PAYMENTS_TEMPORAL_NAMESPACE = os.getenv("PAYMENTS_TEMPORAL_NAMESPACE", "payments")

_WORKFLOW_TYPE = "PaymentCorrectionCoordinator"


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire the same local-only way the other components do."""
    return logfire.configure(service_name="payment-corridor", send_to_logfire=False)


# NOTE: Configure Logfire before instrumenting the app, in the process that
# serves requests (the uvicorn reload subprocess imports this module, not
# main_api.py).
setup_logfire()


def _workflow_id(payment_id: str) -> str:
    """The coordinator's deterministic workflow id for a payment."""
    return f"correction-{payment_id}"


# region FEATURE-OFF: human-approval-signal
async def _query_awaiting(handle) -> bool:
    """No awaiting state until human-approval-signal is enabled."""
    return False


# endregion FEATURE-OFF: human-approval-signal
# region FEATURE-ON: human-approval-signal
# async def _query_awaiting(handle) -> bool:
#     """Ask a running coordinator whether it is blocked on a human decision."""
#     return await handle.query(PaymentCorrectionCoordinator.awaiting_approval)
#
#
# endregion FEATURE-ON: human-approval-signal


class AnomalyAcceptance(BaseModel):
    """Response of POST /anomalies: the accepted request's identifiers."""

    payment_id: str
    workflow_id: str


class AnomalySummary(BaseModel):
    """One row of the in-flight listing."""

    payment_id: str
    corridor: str
    anomaly_type: AnomalyType
    status: str
    workflow_id: str


class AnomalyDetail(BaseModel):
    """Full state of a single correction."""

    payment_id: str
    workflow_id: str
    status: str
    outcome: CorrectionOutcome | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # region FEATURE-OFF: payload-encryption
    # NOTE: PydanticAIPlugin installs the Pydantic data converter so
    # PaymentAnomaly / CorrectionOutcome round-trip identically to the worker.
    # The API needs no Worker and no Prometheus runtime.
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=PAYMENTS_TEMPORAL_NAMESPACE,
        plugins=[PydanticAIPlugin()],
    )
    # endregion FEATURE-OFF: payload-encryption
    # region FEATURE-ON: payload-encryption
    # # NOTE: Encrypt every payload crossing the Temporal boundary with a codec-
    # # enabled data converter. PydanticAIPlugin only installs its own data
    # # converter when the caller doesn't pass one, so keeping the plugin
    # # alongside an explicit data_converter is safe — verified empirically:
    # # dropping PydanticAIPlugin instead breaks TemporalAgent workflow
    # # sandbox validation at worker start-up. Source:
    # # https://docs.temporal.io/production-deployment/data-encryption
    # key = load_key()
    # if not key:
    #     raise RuntimeError("set CODEC_ENCRYPTION_KEY to enable payload encryption")
    # client = await Client.connect(
    #     TEMPORAL_ADDRESS,
    #     namespace=PAYMENTS_TEMPORAL_NAMESPACE,
    #     data_converter=build_data_converter(EncryptionCodec(key)),
    #     plugins=[PydanticAIPlugin()],
    # )
    # endregion FEATURE-ON: payload-encryption
    app.state.temporal_client = client
    yield


app = FastAPI(title="Payment Corridor API", lifespan=lifespan)
logfire.instrument_fastapi(app)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post(
    "/api/payments/v1/anomalies",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_anomaly(anomaly: PaymentAnomaly) -> AnomalyAcceptance:
    """Accept a cross-border payment anomaly and start its correction.

    NOTE: start_workflow (not execute_workflow) — the API returns as soon as the
    correction is durably started, rather than blocking on the outcome.
    """
    client: Client = app.state.temporal_client
    workflow_id = _workflow_id(anomaly.payment_id)
    try:
        handle = await client.start_workflow(
            PaymentCorrectionCoordinator.run,
            anomaly,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
    except WorkflowAlreadyStartedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A correction for payment '{anomaly.payment_id}' already exists.",
        ) from exc
    return AnomalyAcceptance(payment_id=anomaly.payment_id, workflow_id=handle.id)


@app.get("/api/payments/v1/anomalies")
async def list_anomalies(awaiting_approval: bool = False) -> list[AnomalySummary]:
    """List in-flight corrections; optionally only those awaiting a human.

    Two implementations, toggled by the ``search-attributes`` feature (REPLACE):
    the baseline lists running executions and reads each one's summary via a
    per-workflow query (the N+1 pattern); enabling search-attributes replaces it
    with a single, server-side-filtered Visibility query.
    """
    client: Client = app.state.temporal_client
    summaries: list[AnomalySummary] = []

    # region FEATURE-OFF: search-attributes
    # NOTE: Client-side listing. Running executions carry only built-in
    # attributes, so corridor/anomaly-type/awaiting state come from one query per
    # workflow (N+1), and the awaiting filter runs here in Python. This is
    # exactly the cost the search-attributes feature removes.
    query = f"WorkflowType = '{_WORKFLOW_TYPE}' AND ExecutionStatus = 'Running'"
    async for wf in client.list_workflows(query=query):
        handle = client.get_workflow_handle(wf.id)
        anomaly = await handle.query(PaymentCorrectionCoordinator.describe_anomaly)
        awaiting = await _query_awaiting(handle)
        if awaiting_approval and not awaiting:
            continue
        summaries.append(
            AnomalySummary(
                payment_id=anomaly.payment_id,
                corridor=anomaly.corridor,
                anomaly_type=anomaly.anomaly_type,
                status="awaiting-approval" if awaiting else "processing",
                workflow_id=wf.id,
            )
        )
    # endregion FEATURE-OFF: search-attributes

    # region FEATURE-ON: search-attributes
    # # NOTE: Server-side listing. The corridor/anomalyType/status search
    # # attributes are already on each execution, and the awaiting filter is
    # # pushed into the Visibility query — one round-trip, no per-workflow query.
    # from temporalio.common import SearchAttributeKey
    #
    # query = f"WorkflowType = '{_WORKFLOW_TYPE}' AND ExecutionStatus = 'Running'"
    # if awaiting_approval:
    #     query += " AND status = 'awaiting-approval'"
    # async for wf in client.list_workflows(query=query):
    #     sa = wf.typed_search_attributes
    #     corridor = sa.get(SearchAttributeKey.for_keyword("corridor")) or ""
    #     anomaly_type = sa.get(SearchAttributeKey.for_keyword("anomalyType")) or ""
    #     wf_status = sa.get(SearchAttributeKey.for_keyword("status")) or "processing"
    #     summaries.append(
    #         AnomalySummary(
    #             payment_id=wf.id.removeprefix("correction-"),
    #             corridor=corridor,
    #             anomaly_type=AnomalyType(anomaly_type),
    #             status=wf_status,
    #             workflow_id=wf.id,
    #         )
    #     )
    # endregion FEATURE-ON: search-attributes

    return summaries


@app.get("/api/payments/v1/anomalies/{payment_id}")
async def get_anomaly(payment_id: str) -> AnomalyDetail:
    """Return the full state of one correction (404 if unknown)."""
    client: Client = app.state.temporal_client
    workflow_id = _workflow_id(payment_id)
    handle = client.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
    except RPCError as exc:
        if exc.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No correction found for payment '{payment_id}'.",
            ) from exc
        raise

    if desc.status == WorkflowExecutionStatus.COMPLETED:
        outcome: CorrectionOutcome = await handle.result()
        return AnomalyDetail(
            payment_id=payment_id,
            workflow_id=workflow_id,
            status="completed",
            outcome=outcome,
        )
    return AnomalyDetail(
        payment_id=payment_id,
        workflow_id=workflow_id,
        status="running",
    )


# region FEATURE-ON: human-approval-signal
# @app.post(
#     "/api/payments/v1/anomalies/{payment_id}/approval",
#     status_code=status.HTTP_202_ACCEPTED,
# )
# async def approve_anomaly(payment_id: str, decision: ApprovalDecision) -> None:
#     """Relay a human approve/reject verdict to a waiting correction.
#
#     NOTE: fire-and-forget signal — it returns once delivered; the coordinator
#     resumes and finishes asynchronously. Only present when human-approval-signal
#     is enabled (the approve_correction signal exists only then).
#     """
#     client: Client = app.state.temporal_client
#     handle = client.get_workflow_handle(_workflow_id(payment_id))
#     await handle.signal(PaymentCorrectionCoordinator.approve_correction, decision)
#
#
# endregion FEATURE-ON: human-approval-signal
