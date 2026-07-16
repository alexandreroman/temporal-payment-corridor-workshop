"""Client script: simulate an incoming payment anomaly.

Starts a ``PaymentCorrectionCoordinator`` execution and prints the outcome.
Pick what to send with ``--scenario NAME`` (see ``--list-scenarios``); the
default ``memory-hit`` scenario matches a pre-seeded corridor-memory pattern,
so it is corrected end-to-end without any LLM call (no API key required). The
scenario definitions live in ``simulator/scenarios.py``.

Run with:  ``uv run simulator``  (payments and the dev server must be running).
"""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

# region FEATURE-ON: payload-encryption
# from shared.encryption import EncryptionCodec, build_data_converter, load_key
#
# endregion FEATURE-ON: payload-encryption
from simulator.scenarios import DEFAULT_SCENARIO, SCENARIOS, Scenario, build_anomaly
from payments.workflows import TASK_QUEUE, PaymentCorrectionCoordinator

# Configuration from environment / local .env (see .env.example).
load_dotenv()

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
# NOTE: start the coordinator in the same namespace as payments, distinct
# from the memory service's namespace.
PAYMENTS_TEMPORAL_NAMESPACE = os.getenv("PAYMENTS_TEMPORAL_NAMESPACE", "payments")


async def main(scenario: Scenario) -> None:
    # Leading, self-describing line so a captured run names the scenario it ran.
    print(f"scenario: {scenario.name}")

    # region FEATURE-OFF: payload-encryption
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=PAYMENTS_TEMPORAL_NAMESPACE,
        # Same data converter as payments, so Pydantic models round-trip.
        plugins=[PydanticAIPlugin()],
    )
    # endregion FEATURE-OFF: payload-encryption
    # region FEATURE-ON: payload-encryption
    # # NOTE: Encrypt payloads across the Temporal boundary, matching payments'
    # # data converter. PydanticAIPlugin only installs its own data converter
    # # when the caller doesn't pass one, so keeping the plugin alongside an
    # # explicit data_converter is safe — verified empirically: dropping
    # # PydanticAIPlugin instead breaks TemporalAgent workflow sandbox
    # # validation at worker start-up. Source:
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

    anomaly = build_anomaly(scenario)

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

    # NOTE: teaching aside (always-on documentation, not a toggleable feature block):
    # once the `human-approval-signal` feature is enabled in payments, a
    # proposal whose confidence is below CONFIDENCE_THRESHOLD is no longer
    # applied automatically. Instead the coordinator pauses and waits for a
    # human verdict, which arrives out-of-band — sent by a *separate* client,
    # not by this simulator (which only starts the workflow and awaits its
    # result). For example, an ops process holding a workflow handle can
    # approve the correction with:
    #
    #     handle = client.get_workflow_handle(f"correction-{payment_id}")
    #     await handle.signal(
    #         PaymentCorrectionCoordinator.approve_correction,
    #         ApprovalDecision(approved=True, approver="ops@bank.example"),
    #     )
    #
    # or straight from the Temporal CLI:
    #
    #     temporal workflow signal \
    #         --workflow-id correction-<payment_id> \
    #         --name approve_correction \
    #         --input '{"approved": true, "approver": "ops@bank.example"}'
    #
    # Source: https://docs.temporal.io/develop/python/message-passing#send-signal-from-client


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Isolated so tests can exercise argument parsing."""
    parser = argparse.ArgumentParser(
        prog="simulator",
        description="Simulate an incoming payment anomaly and print the correction outcome.",
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS),
        default=DEFAULT_SCENARIO,
        help=f"named anomaly to send (default: {DEFAULT_SCENARIO})",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="list the available scenarios and exit without contacting Temporal",
    )
    return parser


def _print_scenarios() -> None:
    """Print each scenario's name, whether it reaches the agents, and its description."""
    for scenario in SCENARIOS.values():
        reaches = "reaches agents" if scenario.reaches_agents else "offline (no agents)"
        print(f"{scenario.name:<16}{reaches:<22}{scenario.description}")


def cli() -> None:
    """Console-script entry point (`uv run simulator`)."""
    args = _build_parser().parse_args()
    if args.list_scenarios:
        _print_scenarios()
        return
    asyncio.run(main(SCENARIOS[args.scenario]))


if __name__ == "__main__":
    cli()
