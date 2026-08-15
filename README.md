# SPC FlexC for Home Assistant

Experimental local Home Assistant integration for Siemens / Vanderbilt / Comelit SPC panels using the FlexC receiver protocol.

## Project status

This repository is an **implementation scaffold**, not yet a production-ready alarm integration.

The protocol work already validated in the test prototypes includes:

- FlexC TCP session and connection handshake.
- `POLL` `0x20` / `POLL_ACK` `0x21`.
- spontaneous `EVENT` `0x60` / `EVENT_ACK` `0x61`.
- FLEXML `DATA` `0x80` / `DATA_ACK` `0x81`.
- AES-256-CBC encrypted frames and SHA-1 integrity validation.
- batched `CMD_GET_ZONE_STATUS`.
- batched `CMD_GET_AREA_STATUS`.
- `CMD_GET_PANEL_SUMMARY`.
- decoding `ZONE_STATUS`, `AREA_STATUS` and `PANEL_SUMMARY`.

The production transport code still has to be ported from the validated prototype scripts into `flexc/connection.py`.

## Intended architecture

One persistent FlexC connection is shared by the entire integration.

- Zones: batch polling, target 1 s.
- Areas: batch polling, target 1 s.
- `PANEL_SUMMARY`: slow polling, approximately 30–60 s.
- `EVENT 0x60`: processed immediately.
- One coordinator/state store publishes the resulting state to Home Assistant.

The integration must acknowledge protocol messages continuously even while application polling is running.

## Proven diagnostics

The following fields have been observed in `PANEL_SUMMARY` and are suitable for diagnostic entities:

- battery voltage
- auxiliary voltage
- auxiliary current
- AC frequency
- RF type/version
- internal/external bell state
- engineering mode
- panel model, firmware and hardware information

Fault/restoration events received through FlexC `0x60` can maintain persistent diagnostic state for validated modem, X-BUS and RF event pairs.

## Optional / not yet proven through native FlexC

The SPC web `controller_status` page exposes additional values, but these must **not** be advertised as native FlexC capabilities until a FlexC command/source is demonstrated:

- battery current
- mains/battery OK state
- AUX/internal-bell/external-bell fuse state
- detailed X-BUS state and number of online devices
- charger state
- modem ready/connection/type/line state
- signal/network/SIM information
- call/SMS counters

The code deliberately leaves room for these capabilities without fabricating entities.

## Safety

The first implementation should remain read-only. Arming, disarming, inhibition, isolation and output-control commands should not be enabled until their exact FlexC command, reply and failure behaviour have been independently validated.

## Installation for development

Copy:

```text
custom_components/spc_flexc
```

to:

```text
/config/custom_components/spc_flexc
```

Restart Home Assistant, then add **SPC FlexC** from Settings → Devices & services.

At this stage the integration will not connect successfully because `flexc/connection.py` is intentionally a transport skeleton.

## Configuration

Planned config-flow fields:

- SPC address
- FlexC listening port (default `52000`)
- 256-bit FlexC encryption key

Do not commit real alarm encryption keys to Git.

## Home Assistant entities

Planned entity groups:

- `alarm_control_panel`: global/area alarm state once command semantics are finalized.
- `binary_sensor`: zones, tamper zones, bells and proven fault states.
- `sensor`: panel electrical diagnostics.
- diagnostic metadata through Home Assistant device information and diagnostics.

Zones such as siren tamper inputs remain zones; they can be represented as tamper-oriented binary sensors based on their discovered/known type rather than pretending they are motion detectors.

The architecture does not assume exactly two areas or a fixed number of zones.

## Development roadmap

1. Port the validated FlexC framing/crypto/session code into `flexc/`.
2. Implement asynchronous persistent connection and reconnect.
3. Add FLEXML request correlation/reassembly.
4. Implement batch zone and area polling.
5. Implement `PANEL_SUMMARY`.
6. Implement spontaneous event state machine.
7. Add Home Assistant entities and dynamic discovery.
8. Add diagnostics and stale/unavailable handling.
9. Only then evaluate write/control commands.

## License

No license has been selected yet. Add a `LICENSE` file before publishing if you want others to reuse or redistribute the project.
