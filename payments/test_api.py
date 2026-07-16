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

These tests cover the baseline: ``search-attributes`` OFF (the client-side
N+1 listing that reads each running workflow via the ``describe_anomaly`` query,
with ``_query_awaiting`` a no-op returning False) and ``human-approval-signal``
OFF (no ``/approval`` route). Most feature-gated variants are toggled in and
verified elsewhere; the exception is the ``human-approval-signal`` detail-route
test below (in its own ``FEATURE-ON`` region), which reuses this file's httpx/
ASGITransport harness rather than duplicating it in a separate module.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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

# region FEATURE-ON: human-approval-signal
# from shared.models import ComplianceVerdict, ReviewState
# endregion FEATURE-ON: human-approval-signal

# ASGITransport ignores the host, but httpx still needs an absolute base URL to
# build request URLs from the relative paths below.
_BASE_URL = "http://payments.test"


def _wf(workflow_id: str, minutes_ago: int) -> SimpleNamespace:
    """A stub list_workflows row with an id and a start time."""
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=workflow_id,
        start_time=base - timedelta(minutes=minutes_ago),
        typed_search_attributes=TypedSearchAttributes.empty,
    )


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
            agent_name="instruction_agent",
            field_to_fix="bic",
            proposed_value="HDFCINBBXXX",
            rationale="Matched a known corridor pattern in passive memory.",
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
        # region FEATURE-ON: human-approval-signal
        # review: ReviewState | None = None,
        # endregion FEATURE-ON: human-approval-signal
    ) -> None:
        self.id = workflow_id
        self._anomaly = anomaly
        self._describe_status = describe_status
        self._describe_error = describe_error
        self._result = result
        # region FEATURE-ON: human-approval-signal
        # self._review = review
        # endregion FEATURE-ON: human-approval-signal
        # Records whether result() was called, so a test can assert the detail
        # route never fetches an outcome for a closed non-completed run.
        self.result_called = False

    async def query(self, _query):
        # region FEATURE-ON: human-approval-signal
        # if _query is PaymentCorrectionCoordinator.pending_review:
        #     return self._review
        # endregion FEATURE-ON: human-approval-signal
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
            _wf("correction-pay-1", 10),
            _wf("correction-pay-2", 1),
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
    # Newest first: pay-2 (1 minute ago) sorts ahead of pay-1 (10 minutes ago).
    assert response.json() == [
        {
            "payment_id": "pay-2",
            "corridor": "US->IN",
            "anomaly_type": "wrong_bic",
            "status": "processing",
            "workflow_id": "correction-pay-2",
            "start_time": "2019-12-31T23:59:00Z",
            "outcome_summary": None,
        },
        {
            "payment_id": "pay-1",
            "corridor": "US->IN",
            "anomaly_type": "wrong_bic",
            "status": "processing",
            "workflow_id": "correction-pay-1",
            "start_time": "2019-12-31T23:50:00Z",
            "outcome_summary": None,
        },
    ]


def test_list_anomalies_awaiting_filter_is_empty_in_the_baseline():
    """With the human-approval feature off, nothing is ever awaiting approval."""
    stub = _StubClient(
        workflows=[_wf("correction-pay-1", 1)],
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


def test_list_anomalies_awaiting_filter_excludes_closed_rows():
    """A completed row must not leak through the awaiting-approval filter."""
    stub = _StubClient(
        handles={
            "correction-pay-done": _StubHandle(
                "correction-pay-done",
                anomaly=_anomaly("pay-done"),
                describe_status=WorkflowExecutionStatus.COMPLETED,
                result=_outcome("pay-done"),
            ),
            "correction-pay-run": _StubHandle(
                "correction-pay-run", anomaly=_anomaly("pay-run")
            ),
        },
        workflows=[_wf("correction-pay-done", 5), _wf("correction-pay-run", 1)],
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
    # Neither the completed row nor the running-but-not-awaiting row qualifies.
    assert response.json() == []


def test_list_anomalies_sorts_newest_first():
    """Running rows come back ordered by start_time, newest first."""
    handles = {
        "correction-pay-old": _StubHandle(
            "correction-pay-old", anomaly=_anomaly("pay-old")
        ),
        "correction-pay-new": _StubHandle(
            "correction-pay-new", anomaly=_anomaly("pay-new")
        ),
    }
    stub = _StubClient(
        handles=handles,
        workflows=[_wf("correction-pay-old", 10), _wf("correction-pay-new", 1)],
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies")

    response = asyncio.run(scenario())
    ids = [row["payment_id"] for row in response.json()]
    assert ids == ["pay-new", "pay-old"]
    assert response.json()[0]["start_time"] is not None


def test_list_anomalies_includes_recent_completed_with_summary():
    """A recently completed correction lists as applied with a summary line."""
    applied = _StubHandle(
        "correction-pay-done",
        anomaly=_anomaly("pay-done"),
        describe_status=WorkflowExecutionStatus.COMPLETED,
        result=_outcome("pay-done"),  # applied=True in the helper
    )
    running = _StubHandle("correction-pay-run", anomaly=_anomaly("pay-run"))
    stub = _StubClient(
        handles={
            "correction-pay-done": applied,
            "correction-pay-run": running,
        },
        workflows=[_wf("correction-pay-done", 5), _wf("correction-pay-run", 1)],
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies")

    rows = {r["payment_id"]: r for r in asyncio.run(scenario()).json()}
    assert rows["pay-done"]["status"] == "applied"
    assert rows["pay-done"]["outcome_summary"]
    assert rows["pay-run"]["status"] == "processing"
    assert rows["pay-run"]["outcome_summary"] is None


def test_list_anomalies_caps_at_20_newest_rows():
    """The default listing caps at 20 rows, dropping the oldest beyond that."""
    workflow_ids = [f"correction-pay-{i}" for i in range(21)]
    handles = {
        wid: _StubHandle(wid, anomaly=_anomaly(wid.removeprefix("correction-")))
        for wid in workflow_ids
    }
    # pay-0 is newest (0 minutes ago); pay-20 is oldest (20 minutes ago), matching
    # the newest-first order the "ORDER BY StartTime DESC" query relies on.
    workflows = [_wf(wid, minutes_ago) for minutes_ago, wid in enumerate(workflow_ids)]
    stub = _StubClient(handles=handles, workflows=workflows)
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies")

    response = asyncio.run(scenario())

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 20
    # pay-20 (the oldest of the 21 stubbed rows) is the one dropped by the cap.
    assert [row["payment_id"] for row in rows] == [f"pay-{i}" for i in range(20)]


def test_list_anomalies_cap_does_not_evict_an_old_awaiting_row(monkeypatch):
    """An old awaiting row survives the cap behind 20 newer non-awaiting rows.

    Regression test for the cap-before-filter bug: `seen` must count only rows
    the loop actually emits. If it counted every execution list_workflows
    yields (before the awaiting-approval continue-guard runs), 20 newer
    non-awaiting rows would exhaust the cap before the loop ever reaches this
    older, genuinely-awaiting row.
    """
    old_awaiting_id = "correction-pay-old"
    newer_ids = [f"correction-pay-{i}" for i in range(20)]

    handles = {
        old_awaiting_id: _StubHandle(old_awaiting_id, anomaly=_anomaly("pay-old")),
    }
    for wid in newer_ids:
        handles[wid] = _StubHandle(
            wid, anomaly=_anomaly(wid.removeprefix("correction-"))
        )

    # Newest first: the 20 newer rows (0..19 minutes ago), then the much older
    # awaiting row last, mirroring what "ORDER BY StartTime DESC" would yield.
    workflows = [_wf(wid, minutes_ago) for minutes_ago, wid in enumerate(newer_ids)]
    workflows.append(_wf(old_awaiting_id, 1_000))
    stub = _StubClient(handles=handles, workflows=workflows)
    api.app.state.temporal_client = stub

    # The baseline's _query_awaiting is a no-op returning False; stand in for
    # human-approval-signal here so exactly the old row reports as awaiting.
    async def fake_query_awaiting(handle) -> bool:
        return handle.id == old_awaiting_id

    monkeypatch.setattr(api, "_query_awaiting", fake_query_awaiting)

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get(
                "/api/payments/v1/anomalies",
                params={"awaiting_approval": "true"},
            )

    response = asyncio.run(scenario())

    assert response.status_code == 200
    ids = [row["payment_id"] for row in response.json()]
    assert ids == ["pay-old"]


def test_list_anomalies_includes_a_failed_row_with_execution_status():
    """A failed correction lists with the closed-execution status and summary."""
    failed = _StubHandle(
        "correction-pay-failed",
        anomaly=_anomaly("pay-failed"),
        describe_status=WorkflowExecutionStatus.FAILED,
    )
    stub = _StubClient(
        handles={"correction-pay-failed": failed},
        workflows=[_wf("correction-pay-failed", 1)],
    )
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies")

    rows = asyncio.run(scenario()).json()

    assert len(rows) == 1
    # Matches the _CLOSED_NON_COMPLETED branch in list_anomalies exactly:
    # closed_status = desc.status.name.lower().replace("_", "-").
    assert rows[0]["status"] == "failed"
    assert rows[0]["outcome_summary"] == "execution failed"


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
        "review": None,
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
        "review": None,
    }
    # result() raises on a closed non-completed run, so the route must skip it.
    assert handle.result_called is False


def test_get_anomaly_detail_has_null_review_in_baseline():
    """The detail response carries review: null until human-approval-signal ships."""
    handle = _StubHandle(
        "correction-pay-1",
        describe_status=WorkflowExecutionStatus.RUNNING,
    )
    stub = _StubClient(handles={"correction-pay-1": handle})
    api.app.state.temporal_client = stub

    async def scenario() -> httpx.Response:
        async with _http_client() as client:
            return await client.get("/api/payments/v1/anomalies/pay-1")

    body = asyncio.run(scenario()).json()
    assert body["review"] is None


# region FEATURE-ON: human-approval-signal
# def test_get_anomaly_returns_pending_review_while_awaiting():
#     """A running, awaiting-approval correction surfaces its pending review."""
#     review = ReviewState(
#         proposal=CorrectionProposal(
#             agent_name="instruction_agent",
#             field_to_fix="bic",
#             proposed_value="HDFCINBBXXX",
#             rationale="Matched a known corridor pattern in passive memory.",
#             confidence=0.95,
#             source=CorrectionSource.MEMORY,
#         ),
#         verdict=ComplianceVerdict(
#             compliant=False,
#             violations=["sanctions hit"],
#             confidence=0.9,
#             source=CorrectionSource.MEMORY,
#         ),
#     )
#     handle = _StubHandle(
#         "correction-pay-1",
#         describe_status=WorkflowExecutionStatus.RUNNING,
#         review=review,
#     )
#     stub = _StubClient(handles={"correction-pay-1": handle})
#     api.app.state.temporal_client = stub
#
#     async def scenario() -> httpx.Response:
#         async with _http_client() as client:
#             return await client.get("/api/payments/v1/anomalies/pay-1")
#
#     body = asyncio.run(scenario()).json()
#
#     assert body["review"] is not None
#     assert body["review"]["proposal"]["proposed_value"] == "HDFCINBBXXX"
#     assert body["review"]["verdict"]["compliant"] is False
#
#
# endregion FEATURE-ON: human-approval-signal


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
