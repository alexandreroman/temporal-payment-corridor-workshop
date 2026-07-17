"""Payments HTTP API application definition.

The payments component ships as two processes sharing this package: the
Temporal worker (payments/main_worker.py) and this HTTP API. The API holds no
Worker — it is a Temporal *client* that starts corrections, lists in-flight
ones over the Visibility API, and relays human approvals.

Server startup lives in payments/main_api.py; this module defines ``app``.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import SearchAttributeKey, WorkflowIDReusePolicy
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
# from shared.models import ApprovalDecision, ReviewState  # noqa: E402
# endregion FEATURE-ON: human-approval-signal

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
PAYMENTS_TEMPORAL_NAMESPACE = os.getenv("PAYMENTS_TEMPORAL_NAMESPACE", "payments")

_WORKFLOW_TYPE = "PaymentCorrectionCoordinator"

# Closed executions that carry no CorrectionOutcome: result() raises on these, so
# the detail route reports the execution status instead of calling it.
_CLOSED_NON_COMPLETED = frozenset(
    {
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELED,
        WorkflowExecutionStatus.TERMINATED,
        WorkflowExecutionStatus.TIMED_OUT,
        WorkflowExecutionStatus.CONTINUED_AS_NEW,
    }
)


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire the same local-only way the other components do."""
    return logfire.configure(service_name="payment-corridor", send_to_logfire=False)


# Configure Logfire before instrumenting the app.
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


def _summarize_outcome(outcome: CorrectionOutcome) -> str:
    """One human line describing how a correction ended."""
    if outcome.applied and outcome.proposal is not None:
        p = outcome.proposal
        return f"fixed {p.field_to_fix} → {p.proposed_value}"
    if outcome.verdict is not None and outcome.verdict.violations:
        return f"held · {outcome.verdict.violations[0]}"
    return outcome.message or "held"


def _outcome_source(outcome: CorrectionOutcome) -> str | None:
    """The correction's source (`memory`/`llm`), when a proposal exists."""
    return outcome.proposal.source.value if outcome.proposal is not None else None


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
    start_time: datetime
    outcome_summary: str | None = None
    # The correction source (`memory` or `llm`) that used to be appended to
    # outcome_summary, now surfaced separately so the Web UI can render it as its
    # own pill. Optional because closed/awaiting rows have no proposal.
    source: str | None = None
    # Payment context shown on every row (amount, currency, beneficiary name),
    # read from the anomaly during listing. Optional so the search-attributes
    # listing path -- which does not carry the full payment -- still validates.
    amount: float | None = None
    currency: str | None = None
    beneficiary: str | None = None
    # The payment as received (free-form fields, e.g. the invalid bic value),
    # so a row can explain WHY it is anomalous. Optional for the same reason as
    # the other payment fields above.
    details: dict[str, str] | None = None


class AnomalyDetail(BaseModel):
    """Full state of a single correction."""

    payment_id: str
    workflow_id: str
    status: str
    outcome: CorrectionOutcome | None = None
    # The payment under correction, surfaced so the approval panel can show
    # what is being changed (amount, beneficiary, original field value).
    # Populated for a running row (see get_anomaly); null once completed/closed.
    anomaly: PaymentAnomaly | None = None
    # region FEATURE-OFF: human-approval-signal
    # NOTE: Typed loosely as `object` rather than `ReviewState`, which the
    # human-approval-signal feature introduces in shared/models.py. Until that
    # feature is enabled there is never a pending review, so this always
    # serializes as `null`.
    review: object | None = None
    # endregion FEATURE-OFF: human-approval-signal
    # region FEATURE-ON: human-approval-signal
    # # NOTE: The pending proposal + verdict for a correction currently held for
    # # approval, populated by get_anomaly() for a running-awaiting execution;
    # # null otherwise (including once approved and resumed).
    # review: ReviewState | None = None
    # endregion FEATURE-ON: human-approval-signal


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

    NOTE: REJECT_DUPLICATE makes the deterministic workflow id
    (correction-<payment_id>) reject any re-submission for the same payment,
    even after an earlier correction has closed. Without it Temporal's default
    policy would let a duplicate of a *closed* run start a fresh execution; the
    contract is that a duplicate is always a conflict, so the reuse policy turns
    it into WorkflowAlreadyStartedError, which the handler below maps to 409.
    Source: https://docs.temporal.io/workflow-execution/workflowid-runid#workflow-id-reuse-policy
    """
    client: Client = app.state.temporal_client
    workflow_id = _workflow_id(anomaly.payment_id)
    try:
        handle = await client.start_workflow(
            PaymentCorrectionCoordinator.run,
            anomaly,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A correction for payment '{anomaly.payment_id}' already exists.",
        ) from exc
    return AnomalyAcceptance(payment_id=anomaly.payment_id, workflow_id=handle.id)


@app.get("/api/payments/v1/anomalies")
async def list_anomalies(awaiting_approval: bool = False) -> list[AnomalySummary]:
    """List corrections: in-flight plus recent closed history.

    Passing ``awaiting_approval`` narrows the result to running corrections
    blocked on a human decision (closed rows never qualify).
    """
    client: Client = app.state.temporal_client
    summaries: list[AnomalySummary] = []

    # NOTE: Client-side listing. Running executions carry only built-in
    # attributes, so corridor/anomaly-type/awaiting state come from one query per
    # workflow (N+1), and the awaiting filter runs here in Python. This is
    # exactly the cost the search-attributes feature removes.
    query = f"WorkflowType = '{_WORKFLOW_TYPE}'"
    seen = 0
    async for wf in client.list_workflows(query=query):
        # NOTE: The dev server's standard Visibility store rejects "ORDER BY"
        # (RPCError: "operation is not supported: 'ORDER BY' clause"), so this
        # query cannot ask Visibility for newest-first order; list_workflows
        # returns executions in the store's default order instead. `seen`
        # counts only rows this loop actually emits -- incremented right
        # before each summaries.append below, never here -- so a row skipped
        # by an awaiting-approval continue-guard never spends a cap slot that
        # a later, genuinely-matching row needed. The summaries.sort() at the
        # tail of this function re-establishes newest-first order for
        # display; it does not change which 20 executions got selected.
        # Source: https://docs.temporal.io/visibility
        if seen >= 20:
            break
        handle = client.get_workflow_handle(wf.id)
        # NOTE: Now that the query lists closed executions too, each row costs a
        # describe() to learn its status, and a completed row costs a further
        # result() -- extra round-trips on top of the per-workflow
        # describe_anomaly query. This cost is inherent to client-side listing:
        # even with search-attributes on, a closed row still needs
        # describe()/result() to recover its outcome, so that feature removes
        # the running-row identity query but not this closed-row cost.
        # NOTE: One unlistable historical execution (e.g. TERMINATED, or a run
        # whose history is no longer available) must not take down the whole
        # listing -- skip just that row rather than letting the exception
        # propagate out of the loop and 500 the endpoint.
        try:
            desc = await handle.describe()
            anomaly = await handle.query(PaymentCorrectionCoordinator.describe_anomaly)
            if desc.status == WorkflowExecutionStatus.COMPLETED:
                # A closed correction is never blocked on a human decision, so the
                # awaiting-approval filter excludes it (README: "keeps only those
                # blocked on a human decision").
                if awaiting_approval:
                    continue
                # NOTE: The Pydantic data converter needs an explicit target type
                # to rebuild a CorrectionOutcome; without one, result() returns a
                # plain dict at runtime (unlike the _StubHandle used in tests,
                # which returns a real CorrectionOutcome). model_validate()
                # normalizes either shape into a CorrectionOutcome, so this line
                # works against both the live server and the tests.
                outcome = CorrectionOutcome.model_validate(await handle.result())
                seen += 1
                summaries.append(
                    AnomalySummary(
                        payment_id=anomaly.payment_id,
                        corridor=anomaly.corridor,
                        anomaly_type=anomaly.anomaly_type,
                        amount=anomaly.amount,
                        currency=anomaly.currency,
                        beneficiary=anomaly.beneficiary.name,
                        details=anomaly.details,
                        status="applied" if outcome.applied else "held",
                        workflow_id=wf.id,
                        start_time=wf.start_time,
                        outcome_summary=_summarize_outcome(outcome),
                        source=_outcome_source(outcome),
                    )
                )
            elif desc.status in _CLOSED_NON_COMPLETED:
                # Closed rows are never awaiting a human either; same filter as
                # above.
                if awaiting_approval:
                    continue
                closed_status = desc.status.name.lower().replace("_", "-")
                seen += 1
                summaries.append(
                    AnomalySummary(
                        payment_id=anomaly.payment_id,
                        corridor=anomaly.corridor,
                        anomaly_type=anomaly.anomaly_type,
                        amount=anomaly.amount,
                        currency=anomaly.currency,
                        beneficiary=anomaly.beneficiary.name,
                        details=anomaly.details,
                        status=closed_status,
                        workflow_id=wf.id,
                        start_time=wf.start_time,
                        outcome_summary=f"execution {closed_status}",
                    )
                )
            else:
                awaiting = await _query_awaiting(handle)
                if awaiting_approval and not awaiting:
                    continue
                seen += 1
                summaries.append(
                    AnomalySummary(
                        payment_id=anomaly.payment_id,
                        corridor=anomaly.corridor,
                        anomaly_type=anomaly.anomaly_type,
                        amount=anomaly.amount,
                        currency=anomaly.currency,
                        beneficiary=anomaly.beneficiary.name,
                        details=anomaly.details,
                        status="awaiting-approval" if awaiting else "processing",
                        workflow_id=wf.id,
                        start_time=wf.start_time,
                    )
                )
        except Exception as exc:
            logfire.warning(
                "Skipping unlistable execution {workflow_id}: {error}",
                workflow_id=wf.id,
                error=str(exc),
                _exc_info=exc,
            )
            continue

    # NOTE: Newest-first ordering so the web UI's homepage shows the most
    # recent anomalies at the top without any client-side sorting.
    summaries.sort(key=lambda s: s.start_time, reverse=True)

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

    # NOTE: A closed-but-not-completed run (failed, terminated, canceled, timed
    # out, continued as new) produced no CorrectionOutcome, and result() raises
    # on it — so report the execution status verbatim and leave outcome empty.
    if desc.status in _CLOSED_NON_COMPLETED:
        return AnomalyDetail(
            payment_id=payment_id,
            workflow_id=workflow_id,
            status=desc.status.name.lower(),
        )

    # Still running. With search-attributes enabled the coordinator publishes its
    # lifecycle ("processing"/"awaiting-approval") through the status Search
    # Attribute; surface it when present. The read is harmless when the attribute
    # is absent (feature off): get() returns None and we fall back to "running".
    status_sa = desc.typed_search_attributes.get(
        SearchAttributeKey.for_keyword("status")
    )
    review = None
    # region FEATURE-ON: human-approval-signal
    # # NOTE: pending_review() returns non-None only while the coordinator is
    # # blocked on a decision, so this single query both detects the awaiting
    # # state and supplies the payload the approval panel renders -- no separate
    # # _query_awaiting round trip needed here.
    # review = await handle.query(PaymentCorrectionCoordinator.pending_review)
    # endregion FEATURE-ON: human-approval-signal
    # NOTE: The approval panel shows the payment being corrected (amount,
    # beneficiary, original field value), read back through the
    # describe_anomaly query.
    anomaly = await handle.query(PaymentCorrectionCoordinator.describe_anomaly)
    return AnomalyDetail(
        payment_id=payment_id,
        workflow_id=workflow_id,
        status=status_sa or "running",
        review=review,
        anomaly=anomaly,
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
