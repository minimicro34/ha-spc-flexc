"""Read-only FlexC probe for SPC physical-output command discovery.

This deliberately sends GET-style candidate commands only. It never sends an
output-control command and therefore must not change any panel output state.

Run this from a checkout of ha-spc-flexc after filling the connection values
below with the same values used by the existing local FlexC probes.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET

from custom_components.spc_flexc.flexc.connection import FlexCClient
from custom_components.spc_flexc.flexc.flexml import _build_command_envelope

# Fill these with the same test values used by your existing FlexC probes.
SPC_HOST = "192.168.1.200"
SPC_PORT = 52000
FLEXC_KEY = ""  # 64 hexadecimal characters
COMMAND_USERNAME = "homeassistant"
COMMAND_PASSWORD = ""

OUTPUT_IDS = range(1, 9)

# CMD_GET_OUTPUT_STATUS was already tested on SPC4300 3.14.1 and returned
# RESULT=103, but it is retained as a known-negative baseline.
# The other candidates are intentionally GET/read-only variants only.
CANDIDATES: tuple[tuple[str, str], ...] = (
    ("known-negative", '<CMD_GET_OUTPUT_STATUS OUTPUT_ID="{id}" />'),
    ("output", '<CMD_GET_OUTPUT OUTPUT_ID="{id}" />'),
    ("physical-output-status", '<CMD_GET_PHYSICAL_OUTPUT_STATUS OUTPUT_ID="{id}" />'),
    ("physical-output", '<CMD_GET_PHYSICAL_OUTPUT OUTPUT_ID="{id}" />'),
    ("output-state", '<CMD_GET_OUTPUT_STATE OUTPUT_ID="{id}" />'),
)


def classify_reply(response: str) -> str:
    """Return a compact classification while preserving the raw XML output."""
    try:
        root = ET.fromstring(response)
    except ET.ParseError:
        return "non-XML reply"

    replies = [element for element in root.iter() if element.tag.startswith("REPLY_")]
    if not replies:
        return "no REPLY element"

    parts: list[str] = []
    for reply in replies:
        result = reply.attrib.get("RESULT", "?")
        cmd_result = reply.attrib.get("CMD_RESULT", "?")
        parts.append(f"{reply.tag}: RESULT={result} CMD_RESULT={cmd_result}")
    return "; ".join(parts)


async def probe_candidate(client: FlexCClient, label: str, template: str) -> None:
    """Probe one candidate against physical output IDs 1..8."""
    print("\n" + "=" * 78)
    print(f"CANDIDATE: {label}")
    print("=" * 78)

    for output_id in OUTPUT_IDS:
        body = template.format(id=output_id)
        command = _build_command_envelope(
            body,
            COMMAND_USERNAME,
            COMMAND_PASSWORD,
        )
        try:
            response = await client.async_send_flexml(command)
        except Exception as err:  # Probe: preserve all unexpected failures.
            print(f"OUTPUT {output_id}: EXCEPTION {type(err).__name__}: {err}")
            continue

        print(f"\nOUTPUT {output_id}")
        print(f"TX body: {body}")
        print(f"RX class: {classify_reply(response)}")
        print(f"RX raw: {response}")


async def main() -> None:
    """Run the read-only candidate probe."""
    if len(FLEXC_KEY) != 64 or not COMMAND_PASSWORD:
        raise SystemExit(
            "Fill FLEXC_KEY (64 hex chars) and COMMAND_PASSWORD before running."
        )

    config = {
        "host": SPC_HOST,
        "port": SPC_PORT,
        "key": FLEXC_KEY,
        "command_username": COMMAND_USERNAME,
        "command_password": COMMAND_PASSWORD,
    }
    client = FlexCClient(config)

    try:
        print("=== SPC FlexC physical-output read-only discovery probe ===")
        print(f"Expected SPC IP : {SPC_HOST}")
        print(f"Listening port  : {SPC_PORT}")
        print("Waiting for the SPC to connect...")
        await client.async_ensure_connected()
        print("FlexC session established.")

        for label, template in CANDIDATES:
            await probe_candidate(client, label, template)
    finally:
        await client.async_close()


if __name__ == "__main__":
    asyncio.run(main())
