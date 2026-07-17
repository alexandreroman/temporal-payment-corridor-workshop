"""Client script: simulate an incoming payment anomaly.

Submits an anomaly to the payments HTTP API through the gateway and prints the
accepted payment/workflow identifiers. Pick what to send with ``--scenario
NAME`` (see ``--list-scenarios``); the default ``memory-hit`` scenario matches a
pre-seeded corridor-memory pattern, so it is corrected end-to-end without any
LLM call (no API key required). The scenario definitions live in
``simulator/scenarios.py``.

Run with:  ``uv run simulator``  (payments and the dev server must be running).
"""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from dotenv import load_dotenv

from simulator.scenarios import DEFAULT_SCENARIO, SCENARIOS, Scenario, build_anomaly

# Configuration from environment / local .env (see .env.example).
load_dotenv()

GATEWAY_HOST = os.getenv("GATEWAY_HOST", "localhost")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8080"))
# Base URL of the payments API, reached through the gateway (see .env.example).
_API_BASE = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/payments/v1"


async def main(scenario: Scenario) -> None:
    # Leading, self-describing line so a captured run names the scenario it ran.
    print(f"scenario: {scenario.name}")

    anomaly = build_anomaly(scenario)

    # NOTE: Submit through the gateway — the single external entry point — the
    # same path any real client uses. The API starts the correction; the
    # simulator does not talk to Temporal directly.
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{_API_BASE}/anomalies", json=anomaly.model_dump(mode="json")
        )
        resp.raise_for_status()
        acceptance = resp.json()

    print(f"payment : {acceptance['payment_id']}")
    print(f"workflow: {acceptance['workflow_id']}")
    print(f"accepted: submitted to {_API_BASE}/anomalies")

    # NOTE: teaching aside (always-on documentation, not a toggleable feature block):
    # once the `human-approval-signal` feature is enabled in payments, a
    # proposal whose confidence is below CONFIDENCE_THRESHOLD is no longer
    # applied automatically. Instead the coordinator pauses and waits for a
    # human verdict, which arrives out-of-band — sent by a *separate* client,
    # not by this simulator (which only submits the anomaly and returns the
    # accepted identifiers). For example, an ops process can approve the
    # correction through the same gateway API, POSTing the verdict to the
    # approval endpoint:
    #
    #     POST /api/payments/v1/anomalies/<payment_id>/approval
    #     {"approved": true, "approver": "ops@bank.example"}
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
