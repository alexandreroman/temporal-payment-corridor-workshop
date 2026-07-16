"""Tests for the payments HTTP API routes (the baseline, all features off).

Exercise the ``/api/payments/v1`` contract end-to-end against the FastAPI app,
with no network and no live Temporal server. An httpx ``AsyncClient`` speaks to
the app in-process through ``ASGITransport`` (same technique as
``memory/test_app.py``); ASGITransport does not run the lifespan, so
``Client.connect`` is never called — each test stashes a stub Temporal client on
``app.state.temporal_client`` instead, exactly where the real lifespan would.

No ``pytest-asyncio`` dependency is configured (see ``pyproject.toml``), so the
async scenarios are driven with ``asyncio.run`` inside plain synchronous test
functions — the same style as ``memory/test_app.py``.

These tests cover the baseline only: ``search-attributes`` OFF (the client-side
N+1 listing that reads each running workflow via the ``describe_anomaly`` query,
with ``_query_awaiting`` a no-op returning False) and ``human-approval-signal``
OFF (no ``/approval`` route). The feature-gated variants are toggled in and
verified elsewhere.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx

from temporalio.client import WorkflowExecutionStatus
from temporalio.common import TypedSearchAttributes, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from payments import api
from payments.workflows import TASK_QUEUE, PaymentCorrectionCoordinator
from shared.models import (
    AnomalyType,
    CorrectionOutcome,
    CorrectionProposal,
    CorrectionSource,
    PaymentAnomaly,
)

# ASGITransport ignores the host, but httpx still needs an absolute base URL to
# build request URLs from the relative paths below.
_BASE_URL = "http://payments.test"


def _anomaly(payment_id: str = "pay-1") -> PaymentAnomaly:
    """A representative anomaly used across the POST/listing scenarios."""
    return PaymentAnomaly(
        payment_id=payment_id,
        corridor="US->IN",
        amount=500.0,
        currency="INR",
        anomaly_type=AnomalyType.WRONG_BIC,
        details={"bic": "WRONG"},
    )


def _outcome(payment_id: str = "pay-1") -> CorrectionOutcome:
    """A completed correction outcome for the detail scenario."""
    return CorrectionOutcome(
        payment_id=payment_id,
        applied=True,
        proposal=CorrectionProposal(
            agent_name="compliance_agent",
            field_to_fix="bic",
            proposed_value="HDFCINBBXXX",
            rationale="Known corridor pattern.",
            confidence=0.95,
            source=CorrectionSource.MEMORY,
        ),
    )


class _StubHandle:
    """A workflow-handle stand-in returning canned describe/result/query data."""

    def __init__(
        self,
        workflow_id: str,
        *,
        anomaly: PaymentAnomaly | None = None,
        describe_status: WorkflowExecutionStatus | None = None,
        describe_error: Exception | None = None,
        result: CorrectionOutcome | None = None,
    ) -> None:
        self.id = workflow_id
        self._anomaly = anomaly
        self._describe_status = describe_status
        self._describe_error = describe_error
        self._result = result
        # Records whether result() was called, so a test can assert the detail
        # route never fetches an outcome for a closed non-completed run.
        self.result_called = False

    async def query(self, _query):
        # The baseline listing only ever queries describe_anomaly; the awaiting
        # state comes from _query_awaiting (a no-op returning False), not a query.
        return self._anomaly

    async def describe(self):
        if self._describe_error is not None:
            raise self._describe_error
        # Running executions carry no status Search Attribute in the baseline, so
        # an empty attribute set mirrors the search-attributes-off detail path.
        return SimpleNamespace(
            status=self._describe_status,
            typed_search_attributes=TypedSearchAttributes.empty,
        )

    async def result(self) -> CorrectionOutcome:
        self.result_called = True
        assert self._result is not None
        return self._result


class _StartCall:
    """One captured ``start_workflow`` invocation, for later assertions."""

    def __init__(self, run, arg, workflow_id, task_queue, id_reuse_policy) -> None:
        self.run = run
        self.arg = arg
        self.workflow_id = workflow_id
        self.task_queue = task_queue
        self.id_reuse_policy = id_reuse_policy


class _StubClient:
    """A Temporal-client stand-in that captures starts and serves stub handles.

    Wired onto ``app.state.temporal_client`` per test in place of the real
    client the lifespan would connect, so the routes run without a Temporal
    server.
    """

    def __init__(
        self,
        *,
        start_error: Exception | None = None,
        handles: dict[str, _StubHandle] | None = None,
        workflows: list[SimpleNamespace] | None = None,
    ) -> None:
        self.started: list[_StartCall] = []
        self.list_query: str | None = None
        self._start_error = start_error
        self._handles = handles or {}
        self._workflows = workflows or []

    async def start_workflow(self, run, arg, *, id, task_queue, id_reuse_policy):
        self.started.append(_StartCall(run, arg, id, task_queue, id_reuse_policy))
        if self._start_error is not None:
            raise self._start_error
        return _StubHandle(id)

    def get_workflow_handle(self, workflow_id: str) -> _StubHandle:
        return self._handles[workflow_id]

    async def list_workflows(self, query: str | None = None):
        self.list_query = query
        for workflow in self._workflows:
            yield workflow


def _http_client() -> httpx.AsyncClient:
    """Build an httpx client wired straight to the app, no sockets involved."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app), base_url=_BASE_URL
    )


def test_submit_anomaly_starts_the_correction_workflow():
    """POST accepts an anomaly and starts the coordinator with the right ids."""
    stub = _StubClient()
    api.app.state.temporal_client = stub
    anomaly = _anomaly()

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.post(
                "/api/payments/v1/anomalies",
                json=anomaly.model_dump(mode="json"),
            )

    response = asyncio.run(scenario())

    assert response.status_code == 202
    assert response.json() == {
        "payment_id": "pay-1",
        "workflow_id": "correction-pay-1",
    }

    assert len(stub.started) == 1
    call = stub.started[0]
    assert call.run == PaymentCorrectionCoordinator.run
    assert call.workflow_id == "correction-pay-1"
    assert call.task_queue == TASK_QUEUE
    # REJECT_DUPLICATE is what turns a re-submission of a closed run into a 409.
    assert call.id_reuse_policy == WorkflowIDReusePolicy.REJECT_DUPLICATE
    # The posted JSON round-trips back to the exact model start_workflow receives.
    assert call.arg == anomaly


def test_submit_duplicate_anomaly_returns_409():
    """A duplicate correction surfaces as HTTP 409 Conflict."""
    stub = _StubClient(
        start_error=WorkflowAlreadyStartedError(
            "correction-pay-1", "PaymentCorrectionCoordinator"
        )
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.post(
                "/api/payments/v1/anomalies",
                json=_anomaly().model_dump(mode="json"),
            )

    response = asyncio.run(scenario())

    assert response.status_code == 409


def test_list_anomalies_reads_each_running_workflow_via_query():
    """The baseline listing yields one summary per running workflow (N+1 path)."""
    first = _anomaly("pay-1")
    second = _anomaly("pay-2")
    stub = _StubClient(
        workflows=[
            SimpleNamespace(id="correction-pay-1"),
            SimpleNamespace(id="correction-pay-2"),
        ],
        handles={
            "correction-pay-1": _StubHandle("correction-pay-1", anomaly=first),
            "correction-pay-2": _StubHandle("correction-pay-2", anomaly=second),
        },
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies")

    response = asyncio.run(scenario())

    assert response.status_code == 200
    assert response.json() == [
        {
            "payment_id": "pay-1",
            "corridor": "US->IN",
            "anomaly_type": "wrong_bic",
            "status": "processing",
            "workflow_id": "correction-pay-1",
        },
        {
            "payment_id": "pay-2",
            "corridor": "US->IN",
            "anomaly_type": "wrong_bic",
            "status": "processing",
            "workflow_id": "correction-pay-2",
        },
    ]


def test_list_anomalies_awaiting_filter_is_empty_in_the_baseline():
    """With the human-approval feature off, nothing is ever awaiting approval."""
    stub = _StubClient(
        workflows=[SimpleNamespace(id="correction-pay-1")],
        handles={
            "correction-pay-1": _StubHandle(
                "correction-pay-1", anomaly=_anomaly("pay-1")
            ),
        },
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get(
                "/api/payments/v1/anomalies",
                params={"awaiting_approval": "true"},
            )

    response = asyncio.run(scenario())

    assert response.status_code == 200
    assert response.json() == []


def test_get_anomaly_reports_running():
    """A still-running correction is reported as running, with no outcome."""
    stub = _StubClient(
        handles={
            "correction-pay-1": _StubHandle(
                "correction-pay-1",
                describe_status=WorkflowExecutionStatus.RUNNING,
            ),
        },
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies/pay-1")

    response = asyncio.run(scenario())

    assert response.status_code == 200
    assert response.json() == {
        "payment_id": "pay-1",
        "workflow_id": "correction-pay-1",
        "status": "running",
        "outcome": None,
    }


def test_get_anomaly_reports_completed_outcome():
    """A completed correction returns its CorrectionOutcome from result()."""
    stub = _StubClient(
        handles={
            "correction-pay-1": _StubHandle(
                "correction-pay-1",
                describe_status=WorkflowExecutionStatus.COMPLETED,
                result=_outcome("pay-1"),
            ),
        },
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies/pay-1")

    response = asyncio.run(scenario())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["payment_id"] == "pay-1"
    assert body["workflow_id"] == "correction-pay-1"
    assert body["outcome"]["applied"] is True
    assert body["outcome"]["proposal"]["proposed_value"] == "HDFCINBBXXX"


def test_get_anomaly_reports_a_closed_non_completed_state():
    """A failed correction reports its execution status and never calls result()."""
    handle = _StubHandle(
        "correction-pay-1",
        describe_status=WorkflowExecutionStatus.FAILED,
    )
    stub = _StubClient(handles={"correction-pay-1": handle})
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies/pay-1")

    response = asyncio.run(scenario())

    assert response.status_code == 200
    assert response.json() == {
        "payment_id": "pay-1",
        "workflow_id": "correction-pay-1",
        "status": "failed",
        "outcome": None,
    }
    # result() raises on a closed non-completed run, so the route must skip it.
    assert handle.result_called is False


def test_get_unknown_anomaly_returns_404():
    """An unknown payment id (NOT_FOUND from describe) surfaces as HTTP 404."""
    stub = _StubClient(
        handles={
            "correction-missing": _StubHandle(
                "correction-missing",
                describe_error=RPCError(
                    "workflow not found", RPCStatusCode.NOT_FOUND, b""
                ),
            ),
        },
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies/missing")

    response = asyncio.run(scenario())

    assert response.status_code == 404
