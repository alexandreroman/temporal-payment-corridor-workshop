"""Worker entrypoint.

Order matters here. The Temporal ``Runtime`` (with its Prometheus metrics
exporter) is created *first*, before any client or worker, so that the SDK
metrics registry is wired up before any other Temporal code runs. The same
runtime backs the application metrics emitted from the activities, so a
single ``/metrics`` endpoint serves both:

  * Temporal SDK / worker metrics  -> ``temporal_*``
  * Application metrics             -> ``corridor_*``

Run with:  ``uv run worker``  (needs ``temporal server start-dev`` up).
"""

from __future__ import annotations

import asyncio
import os

import logfire
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.runtime import PrometheusConfig, Runtime, TelemetryConfig

from pydantic_ai.durable_exec.temporal import LogfirePlugin, PydanticAIPlugin

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

# Imported after load_dotenv() so .env values (e.g. CORRIDOR_MODEL) are in
# place before agents.py reads them at import time (via the worker.workflows
# -> worker.agents import chain that build_worker pulls in).
from worker.worker import build_worker  # noqa: E402

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
METRICS_BIND_ADDRESS = os.getenv("METRICS_BIND_ADDRESS", "0.0.0.0:9464")


def build_runtime() -> Runtime:
    """Create the Temporal runtime with a Prometheus metrics endpoint.

    Must be called before connecting any client. The exporter serves
    OpenMetrics/Prometheus at ``http://<METRICS_BIND_ADDRESS>/metrics``.
    """
    return Runtime(
        telemetry=TelemetryConfig(
            metrics=PrometheusConfig(bind_address=METRICS_BIND_ADDRESS),
        )
    )


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire + Pydantic AI instrumentation.

    Passed to ``LogfirePlugin`` so the plugin uses this configuration
    instead of its default ``logfire.configure()`` (which would fail with
    no token). ``send_to_logfire='if-token-present'`` keeps the workshop
    offline-friendly: with no ``LOGFIRE_TOKEN`` set, spans are still
    produced locally but nothing is shipped to the Logfire backend.
    """
    instance = logfire.configure(
        service_name="payment-corridor",
        send_to_logfire="if-token-present",
    )
    instance.instrument_pydantic_ai()
    return instance


async def main() -> None:
    runtime = build_runtime()

    client = await Client.connect(
        TEMPORAL_ADDRESS,
        runtime=runtime,
        # PydanticAIPlugin installs the Pydantic data converter and auto-
        # registers each workflow's agents' activities. LogfirePlugin wires
        # Temporal's own tracing into Logfire. metrics=False because SDK and
        # app metrics are already exported via the Prometheus endpoint on the
        # runtime above — we don't want a second, OTel-based metrics pipeline.
        plugins=[
            PydanticAIPlugin(),
            LogfirePlugin(setup_logfire=setup_logfire, metrics=False),
        ],
    )

    worker = build_worker(client)

    print(f"Worker polling '{worker.task_queue}' — metrics on http://{METRICS_BIND_ADDRESS}/metrics")
    await worker.run()


def _run_worker() -> None:
    """Run the worker once. Used as the hot-reload subprocess target."""
    asyncio.run(main())


def dev() -> None:
    """Console-script entry point (`uv run worker`): run with hot reload.

    watchfiles restarts ``_run_worker`` in a fresh subprocess whenever a
    source file changes (it ignores .venv, .git, __pycache__ by default).
    """
    from watchfiles import run_process

    run_process(".", target=_run_worker)


if __name__ == "__main__":
    asyncio.run(main())
