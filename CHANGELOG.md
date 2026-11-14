# Changelog

All notable changes to SPC FlexC are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

---

## [1.1.5] - 2026-11-14

### Added

- Bundled SPC FlexC Card v1.0.28 with expanded System diagnostics, event history details, and a collapsible PIR slow-read section.
- Optional zone tamper and trouble diagnostic entities, with event-driven updates and restoration handling.
- Optional rolling PIR slow-read diagnostic sensor with a one-hour history, maximum duration, and timestamps.
- Additional FlexC event metadata, including reception time and resolved area/zone names.

### Improved

- Faster command handling after unsolicited FlexC EVENT acknowledgements, avoiding unnecessary waits for the next supervision POLL when no command is in flight.
- More responsive access-control door status updates after DRS event #3012.
- Zone polling, event reconciliation, and PIR timing diagnostics; read durations are distinguished from lock and synchronization waits.
- Automatic cleanup of orphaned area, zone, and empty area-device registry entries after complete discovery.

### Fixed

- Schedule PIR diagnostic sensor state updates on the Home Assistant event loop, preventing executor-thread state-write errors.
- Corrected FlexC command-context synchronization and preserved the authoritative DATA reply context for commands already in flight.
- Addressed card display and event-history presentation issues identified during the beta cycle.

### Validation

- Beta.17: 465 Python tests passed, 91.76% coverage; 20 JavaScript tests passed in the beta validation cycle.
- Signed-release dry run reported successful for beta.17.
- Independent production feedback on beta.17: occasional PIR slow reads of approximately 1.0–1.35 s, without repeated failures; frequency decreased after a second test VM/ATS was removed.
- Beta.15 command-context and door-status behavior was validated on a production SPC installation; other hardware-specific features remain dependent on panel model and firmware.

### Known limitations

- Occasional PIR slow reads may still occur, especially when multiple FlexC ATS connections share a panel; the precise cause is not yet confirmed.
- Automatic ATP account assignment when the panel sends account `0` has not been independently confirmed across all supported SPC firmware versions. An explicit nonzero account remains a workaround if the connection closes before the first POLL.

**Full Changelog**: https://github.com/minimicro34/ha-spc-flexc/compare/v1.1.4...v1.1.5

---

## [1.1.5-beta.17]

### Version

- Integration (`manifest.json`): `1.1.5-beta.17`
- SPC FlexC Card: `1.0.28` (unchanged)

### Fixed

- Run the rolling PIR slow-read history refresh callback on the Home Assistant event loop, avoiding unsafe `async_write_ha_state()` calls from an executor thread and the resulting `RuntimeError` log flood.

### Tests

- CI: 465 Python tests passed; 91.76% coverage (80% minimum).
- No dedicated regression test for the callback execution context added yet.

### Validation

- Signed-release dry run passed; live Home Assistant validation pending.

---

## [1.1.5-beta.16]

### Version

- Integration (`manifest.json`): `1.1.5-beta.16`
- SPC FlexC Card: `1.0.28`

### Added

- Optional, disabled-by-default PIR slow-read diagnostic sensor with a rolling one-hour count, maximum read duration and timestamped readings.
- Collapsible PIR diagnostic section in the System tab of the bundled card, below FlexC event history and above RF.

### Improved

- Classify actual PIR zone read latency using DEBUG (1,000–1,499 ms), INFO (1,500–1,999 ms), and WARNING (2,000 ms and above).
- Detect three slow reads within a rolling 60-second window and rate-limit repeated-slow-read warnings to once per ten minutes.
- Keep resynchronization waits and lock delays separate from actual read duration.

### Fixed

- Refresh the optional diagnostic sensor periodically to expire measurements older than one hour.

### Tests

- Added unit tests for read thresholds, repeated warning cooldown and history expiry.
- GitHub Actions CI: 465 Python tests passed (91.76% coverage) and 20 JavaScript tests passed.

### Validation

- Beta15 production confirmation (Ludovic, Cat 5): PIR detections on garage zones 45/46 at 18:33:03 and 18:33:11; automation sent `Door 1 Mode normal` at 18:33:13.666; Door 1 returned to normal at 18:33:13.695 (29 ms). DRS response was immediate; the remaining 5–6 seconds were attributed to Nuki mechanical operation. This validates the beta15 command/polling correction in the reported production scenario, not the new beta16 diagnostics.
- GitHub Actions CI validated: 465 Python tests passed, 91.76% coverage, and 20 JavaScript tests passed.
- Signed release dry run passed; beta.16 PIR diagnostics hardware validation pending.

---

## [1.1.5-beta.15]

### Version

- Integration (`manifest.json`): `1.1.5-beta.15`
- SPC FlexC Card: `1.0.27`

### Improved

- Refresh the idle FlexC command context immediately after acknowledging an unsolicited EVENT, instead of waiting for the next ATP supervision POLL (8–10 seconds depending on path category).
- Preserve the authoritative DATA reply context while a command is in flight; subsequent EVENTs update the idle context using their latest validated transport sequence.

### Fixed

- Avoid unnecessary pre-command EVENT-to-POLL synchronization delays for alarm arm/disarm and read-only status requests.
- Align EVENT/POLL regression tests with the acknowledged-EVENT context behavior, including consecutive events, pending commands, handshake reset, and reported timeout patterns.

### Tests

- 461 Python tests passed in GitHub Actions; coverage 91.86% (80% minimum).
- CI quality checks and coverage completed successfully on commit `1ec8a1c`.

### Validation

- GitHub Actions CI: https://github.com/minimicro34/ha-spc-flexc/actions/runs/42368264306
- Real SPC panel validation remains pending, especially unsolicited PIR EVENT → immediate arm/disarm commands, consecutive EVENTs and reconnects. Keep production on beta.14 until confirmed.

---

## [1.1.5-beta.14]

### Version

- Integration (`manifest.json`): `1.1.5-beta.14`
- SPC FlexC Card: `1.0.27`

### Changed
- Improved the integrated Lovelace card event history layout with more compact rows.
- Updated FlexC event timestamps to include seconds for more precise event tracking.

### Fixed
- Improved DRS door-release responsiveness by triggering an immediate door status refresh when FlexC event `#3012` is received, without waiting for the regular polling cycle.
- Preserved periodic polling as a fallback for door status synchronization.


### Validation
- 458 Python tests passed.
- 20 Lovelace card tests passed.
- Local test coverage: **91.91%**.
- Full local `make check` passed.
- Real hardware validation of DRS event `#3012` and Nuki automation responsiveness is pending.

---

## [1.1.5-beta.13]

## Important — FlexC ATP automatic account assignment

This beta introduces automatic ATP client account assignment for SPC panels configured with account `0`.

Based on the behavior identified in the official SPCLink receiver implementation, the integration now generates a nonzero account identifier and returns it in the encrypted FlexC CONNECT acknowledgement.

This addresses a potential cause of the repeated CONNECT/disconnect cycle observed on an SPC4300 when using ATP account `0`.

**This change requires validation on a real SPC4300.** If the connection still drops before the first POLL, configuring an explicit nonzero ATP account remains the recommended workaround.

### Version

- Integration (`manifest.json`): `1.1.5-beta.13`
- SPC FlexC Card: `1.0.26`

### Added
- Automatic ATP client account assignment for FlexC CONNECT requests using account `0`, supporting legacy and modern connection acknowledgements.
- Additional regression tests covering automatic account assignment, explicit accounts, subsequent acknowledgements and new assignments.

### Fixed
- Removed temporary beta.12 ATP account `0` disconnect warnings and redundant session identity sampling logs.
- Fixed the duplicated event history heading in the bundled Lovelace card. The expandable panel now displays a localized event count (for example, `11 événements`).

### Changed
- Preserved explicitly configured nonzero ATP accounts and existing session identity-change diagnostics.


### Validation
- **451 Python tests passed**
- **92.08% Python coverage** (minimum required: 80%)
- Real SPC4300 validation with ATP account `0` pending.

---

## [1.1.5-beta.12]

### Version

- Integration (`manifest.json`): `1.1.5-beta.12`
- SPC FlexC Card: `1.0.25`

### Added

- Record a UTC reception timestamp (`received_at`) for each recent FlexC event.
- Include discovered area and zone names (`area_name`, `zone_name`) alongside their original numeric identifiers.
- Display event reception times, area names and zone names in the **System** tab of the bundled SPC FlexC Card.
- Show a localized activation hint when the optional **Last FlexC event ID** diagnostic sensor is disabled or unavailable.
- Add regression tests for event metadata and the diagnostic sensor activation hint.

### Improved

- Centralize the card version in `frontend/package.json` as the single source of truth.
- Automatically synchronize the frontend lockfile and generated JavaScript bundle during the build.
- Read the bundled card version dynamically for Lovelace resource cache-busting.
- Preserve numeric event identifiers and existing wireless/X-BUS diagnostics.

### FlexC ATP account `0` diagnostics

- Log incoming `CONNECT` messages using account `0` at DEBUG level.
- Warn when the TCP session closes before receiving its first `POLL`.
- Allow an initial transition from account `0` to a nonzero account on the first `POLL` without a misleading identity-change warning.
- Add regression tests for these scenarios.

**Known limitation:** Automatic ATP client account assignment is not yet validated on the SPC4300. A successful `CONNECT → ACK` exchange does not guarantee a usable FlexC session.

Continue using a manually configured, nonzero ATP client account until this behavior has been validated.


### Validation

- **448 Python tests passed**
- **20 JavaScript card tests passed**
- **92.00% Python coverage** on GitHub Actions (92.05% locally)
- Required coverage threshold: 80%
- Frontend bundle consistency checks included in CI

### Compatibility and limitations

- FlexC encryption and outbound command behavior remain unchanged.
- AES key rotation remains unsupported.
- Recent event history is stored in memory and resets when the integration reloads.
- This is a pre-release intended for testing and feedback.

---

## [1.1.5-beta.11]

### Version

- Integration (`manifest.json`): `1.1.5-beta.11`
- SPC FlexC Card: `1.0.24`

### Fixed

- Automatically remove orphaned SPC area devices from the Home Assistant device registry after complete discovery.
- Preserve devices that still contain registered entities, have child devices, or belong to another configuration entry.
- Automatically remove orphaned area alarm-control entities when the corresponding SPC area no longer exists.
- Automatically clean up orphaned zone entities when their zone is no longer discovered.
- Prevent cleanup when discovery results are incomplete or when entities remain active.

### Validation

- **446 Python tests passed** locally and in GitHub Actions.
- **Python coverage:** 92.07% locally / 92.01% in GitHub Actions.
- **SPC4300 hardware:** confirmed automatic removal of one orphan area entity and six orphan zone entities with beta.10.
- **Pending hardware validation:** automatic removal of the empty orphan area device with beta.11.

### Testing

After installing beta.11, reload the SPC FlexC integration and verify that the orphan `TEST FLEXC` device disappears from Home Assistant without manual deletion.

---

## [1.1.5-beta.10]

### Version

- Integration (`manifest.json`): `1.1.5-beta.10`
- SPC FlexC Card: `1.0.24`

### Fixed

- Automatically remove orphaned SPC area (`alarm_control_panel`) entities after complete discovery when their area no longer exists.
- Preserve active area entities and skip cleanup when no areas are discovered.
- Retain the orphaned zone entity cleanup introduced in beta.9.

### Validation

- **444 Python tests passed** locally and in GitHub Actions.
- **Python coverage:** 92.05% CI / 92.10% locally.
- Automated regression tests added for orphaned area cleanup and empty discovery protection.

### Testing

- Verify that deleting a temporary SPC area removes its unavailable Home Assistant alarm-control entity after integration reload and complete discovery.
- Confirm that existing areas and their alarm-control entities remain unaffected.

---

## [1.1.5-beta.9]

### Version

- Integration (`manifest.json`): `1.1.5-beta.9`
- SPC FlexC Card: `1.0.24`

### Fixed
- Automatically clean up orphaned SPC zone entities after successful background discovery.
- Remove stale zone entities left **unavailable** in Home Assistant when their zone is no longer discovered by the SPC panel.
- Preserve entities belonging to discovered zones and protect entities with active Home Assistant states.
- Skip orphan cleanup when zone discovery returns no zones.

### Diagnostics
- Preserve `FlexC PIR poll slow` warnings after the startup grace period to help investigate occasional slow zone polling and resynchronization delays.

### Validation
- **442 Python tests passed.**
- **18 JavaScript tests passed locally.**
- **92.03% Python coverage** in GitHub Actions (minimum required: 80%).

### Testing notes
- Orphan cleanup runs only after background discovery completes, not immediately when the integration reloads.
- No Home Assistant Core restart is required.
- Existing automations, helpers and dashboards are not automatically modified when orphan entities are removed.
- Testing on a non-production Home Assistant instance is recommended before deployment to a live alarm system.

---

## [1.1.5-beta.8]

### Version

- Integration (`manifest.json`): `1.1.5-beta.8`
- SPC FlexC Card: `1.0.24`

### Added

- Display recent FlexC events in a collapsible System panel.
- Group wireless events in an expandable section, including RF Jamming diagnostics.
- Add per-zone tamper and trouble diagnostic sensors.
- Show detector anomaly indicators and counters in the Lovelace card.

### Changed

- Preserve expanded diagnostic panels across card updates.
- Improve FlexC session identity diagnostics and connection handling.

### Fixed

- Fix an undefined-variable error in detector icon rendering.
- Display a shield-alert icon and explicit Sabotage state for tampered detectors.
- Include ordinary detector tamper events in area sabotage indicators.
- Retry transient Home Assistant entity-registry discovery failures.
- Preserve the Outputs tab while entity discovery is in progress.
- Distinguish loading states from genuinely empty detector lists.
- Preserve latched tamper and trouble observations during ordinary PIR polling.
- Clear pending commands when a TCP session is replaced.
- Correct legacy FlexC CONNECT acknowledgement handling.
- Synchronize bundled card version metadata and Lovelace resource cache version.


### Validation

- Includes Lovelace card regression tests and frontend distribution consistency checks.
- Release candidate intended for validation on Home Assistant.

---

## [1.1.5-beta.7]

### Version

- Integration (`manifest.json`): `1.1.5-beta.7`
- SPC FlexC Card: `1.0.22`

### Fixed

- Fixed the **Wireless (RF)** section in the System tab, which was still displayed as a regular diagnostics list instead of a collapsible panel.
- RF Jamming now appears inside the expandable Wireless (RF) panel, including when its state is `off`.

### Changed

- Aligned the Wireless (RF) panel with the rounded, expandable layout used for FlexC event history.
- Added a count of available RF diagnostics and wireless events to the collapsed panel header.
- Preserved the expanded/collapsed state during Home Assistant card updates.
- Updated the bundled Lovelace card JavaScript.

### Validation

- Frontend distribution bundle synchronized with its source files.
- GitHub Actions CI verification pending.
- Live Home Assistant UI verification pending.

---

## [1.1.5-beta.6]

### Version

- Integration (`manifest.json`): `1.1.5-beta.6`
- SPC FlexC Card: `1.0.22`

### Added

- Added a collapsible **FlexC event history** panel in the **System** tab, displaying the number of recent events.
- Added a dedicated **Wireless (RF)** diagnostics section, including RF Jamming even when its state is `off`.
- Added expandable wireless event details when wireless events are available.

### Changed

- Updated the System tab layout with rounded, expandable diagnostic panels.
- Moved **RF Jamming** into the Wireless (RF) section, removing its duplicate display from the previous location.
- Improved RF Jamming status presentation to distinguish normal, active and unknown states.
- Preserved the expanded/collapsed state of diagnostic panels during Home Assistant updates.
- Updated the bundled Lovelace card JavaScript.

### Validation

- Frontend distribution bundle synchronized with its source files.
- Frontend CI checks passed.
- Live Home Assistant UI validation pending.

---

## [1.1.5-beta.5]

### Version

- Integration (`manifest.json`): `1.1.5-beta.5`
- SPC FlexC Card: `1.0.21`

### Fixed

- Fixed legacy FlexC `CONNECT (0x01)` acknowledgements to echo the SPC account code supplied by the panel instead of using a hardcoded value.
- Clear pending commands when a new TCP session replaces an existing one, preventing stale commands and buffered frames from interfering with the new session.
- Added a 60-second idle read timeout to close stalled or inactive FlexC TCP sessions.
- Improved handling of SPC authentication error `54`.
- Preserve zone tamper and trouble event states across normal PIR polling and physical input changes.
- Avoid unnecessary **PIR poll slow** warnings during the first 30 seconds after zone polling starts. Slow readings remain available at DEBUG level during startup; WARNING-level reporting resumes afterwards.

### Added

**Zone tamper and trouble diagnostics**

- Added two diagnostic binary sensors per discovered SPC zone: **Tamper** and **Trouble**.
- Handle zone-type event families:
  - `1200–1223`: zone tamper.
  - `1300–1323`: zone tamper restored.
  - `1800–1823`: zone trouble.
  - `1900–1923`: zone trouble restored.
- Support corresponding events for different zone types, including `1201/1301`, `1801/1901` and unused-zone variants.
- Prevent events referencing unknown zones from creating phantom entities.
- Preserve the original PIR or door-contact state and icon independently of these diagnostics.

**Enhanced FlexC event diagnostics**

- Extended the optional, disabled-by-default **Last FlexC event ID** sensor with descriptions and classifications for supported events.
- Added decoding for zone input events `2100`, `2101`, `2103` and `2107`, zone tamper/trouble transitions, and validated panic, medical, fire and hold-up events.
- Improved the 20-event diagnostic history with event descriptions, origins and available area/zone identifiers.
- Retained numeric event IDs for events without a known description.
- Added diagnostic support for events originating from wireless devices and X-BUS keypads.

**FlexC session diagnostics**

- Added non-blocking monitoring of SPC account code, connection ID and receiver identifier changes.
- Added sanitized identity diagnostics for incoming CONNECT, POLL, EVENT and DATA messages.
- Added detection of `KEY_UPDATE (0x40)` and `KEY_ACK (0x41)` messages for diagnostic purposes only.

**SPC FlexC Card v1.0.21**

- Added separate tamper and trouble indicators to detector rows.
- Added anomaly counters to detector groups and the general overview.
- Improved the **System** tab with recent FlexC event IDs and descriptions.
- Preserved existing detector icons, physical input states and Wireless/X-BUS diagnostics.
- Added automated JavaScript regression tests for the bundled card.

### Changed

- Learn the active FlexC connection ID from the first POLL instead of assuming a fixed receiver connection ID.
- Avoid misleading session identity warnings during the initial CONNECT-to-POLL transition.
- Keep identity diagnostics non-blocking without changing valid incoming frame processing.
- Improved documentation for event classifications, diagnostic entities and the bundled card.

### Safety and limitations

- Transient alarm events do not automatically latch Home Assistant alarm state without an authoritative SPC state transition.
- Zone tamper/trouble diagnostics reflect observed events and should not be confused with physical PIR motion or door-contact states.
- AES key rotation is **not implemented**. `KEY_UPDATE` and `KEY_ACK` remain diagnostic-only.
- The recent event history is held in memory and resets when the integration reloads.
- Hardware validation of the new zone diagnostics remains ongoing.

### Validation

- **Python:** 432 tests passed.
- **JavaScript:** 18 card tests passed.
- **GitHub Actions CI:** Passed.
- **Python coverage:** 91.96% on GitHub Actions.
- Ruff formatting/lint and automated checks passed.

- **SPC FlexC integration:** `1.1.5-beta.5`
- **Bundled SPC FlexC Card:** `1.0.21`

---

## [1.1.5-beta.4]

### Version

- Integration (`manifest.json`): `1.1.5-beta.4`
- SPC FlexC Card: `1.0.20`

### Added

- Extended the optional, disabled-by-default **Last FlexC event ID** diagnostic sensor with decoded alarm types and transitions for validated panic, medical, fire and hold-up events.
- Added event origin classification for user commands, wireless keypads and X-BUS keypads.
- Extended the recent event history with event descriptions, origins, alarm types and transitions, including events without area or zone identifiers.
- Added automated Node.js regression tests for the bundled Lovelace card, integrated into `make check` through `make card-test`.

### Improved

- Expanded card regression coverage for panel selection, diagnostic isolation, missing entities, HTML escaping and alarm-state presentation.
- Improved documentation for the card testing workflow and diagnostic event classifications.
- Consolidated the upcoming stable release changes in `CHANGELOG.md`, keeping individual beta changes in their GitHub Releases.

### Safety

- Transient panic, medical, fire and hold-up events remain **diagnostic observations**, not persistent Home Assistant alarm states.
- Alarm state changes continue to require authoritative SPC state information.
- Events without area or zone identifiers remain available for diagnostics.

### Validation

- **406 Python tests passed.**
- **18 Node.js card tests passed**, locally and on GitHub Actions.
- **92.11% Python coverage on GitHub Actions.**
- **92.17% Python coverage locally.**
- Local `make check` and `make coverage` passed.
- Hardware validation remains recommended before production use.

### Notes

- No changes to FlexC command handling or AES encryption.
- `KEY_UPDATE (0x40)` and `KEY_ACK (0x41)` remain diagnostic-only; automatic AES key rotation is not implemented.
- The stable release remains `v1.1.4`.

---

## [1.1.5-beta.3]

### Version

- Integration (`manifest.json`): `1.1.5-beta.3`
- SPC FlexC Card: `1.0.19`

### Changed

- Improved FlexC session identity diagnostics to support different connection ID behaviors across SPC panels and firmware versions.
- Learn the active connection ID from the first `POLL (0x20)` instead of assuming a fixed receiver connection ID.
- Avoid misleading identity-change warnings during the initial CONNECT-to-POLL transition.
- Continue reporting unexpected identity changes after the session baseline is established, without rejecting valid frames.
- Preserve per-message-type identity samples introduced in beta.2.

### Tests

- Added regression tests covering legacy `CONNECT (0x00)` and `CONNECT (0x02)`, different connection IDs, and unexpected changes during an established session.
- 364 tests passed.
- CI coverage: 92.08%.
- Local coverage: 92.13%.

### Notes

- No changes to FlexC command handling, outbound frames, or AES encryption.
- `KEY_UPDATE (0x40)` and `KEY_ACK (0x41)` remain diagnostic-only and unsupported.
- The stable release remains `v1.1.4`.

---

## [1.1.5-beta.2]

### Version

- Integration (`manifest.json`): `1.1.5-beta.2`
- SPC FlexC Card: `1.0.19`

### Changed

- Record a sanitized identity sample once per incoming message type and TCP session, including CONNECT, POLL, EVENT and DATA.
- Treat the known receiver connection ID (`0x77359401`) as an informational difference rather than an unexpected identity warning.
- Continue reporting other unexpected changes to `spt_account`, `connection_id` and `rct_identifier`.
- Keep all identity diagnostics non-blocking: incoming frames are still accepted.

### Added

- Explicit detection and logging of `KEY_UPDATE` (`0x40`) and `KEY_ACK` (`0x41`) messages.
- Dedicated regression tests for identity sampling, receiver connection ID handling and key-management messages.

### Important limitations

- AES key rotation is **not implemented**. The integration does not send a `KEY_ACK` or change encryption keys.
- Message-type diagnostics require successful frame decoding.
- Some identity-field semantics remain under investigation and require further hardware validation.

### Validation

- **362 tests passed**
- **92.07% coverage (CI)**
- **92.13% coverage (local)**
- GitHub Actions quality checks passed.

---

## [1.1.5-beta.1]

### Version

- Integration (`manifest.json`): `1.1.5-beta.1`
- SPC FlexC Card: `1.0.19`

### Fixed

- Fixed the legacy FlexC connection acknowledgement (`0x01`) to echo the SPC account code supplied by the panel instead of using a hardcoded value.
- Prevented pending commands from remaining active when a new TCP session replaces the previous connection.
- Prevented stale command timeouts and buffered frames from an old session from interfering with a newer connection.
- Added a 60-second idle read timeout to close inactive or stalled FlexC TCP sessions.
- Improved SPC error handling by distinguishing authentication error `54` from other panel error codes.

### Added

- Non-blocking session identity diagnostics for changes in SPC account code, connection ID and receiver identifier.
- Diagnostic warnings are deduplicated per field and TCP session, without rejecting incoming frames.
- Additional regression tests covering connection acknowledgements, session replacement, timeouts, authentication errors and identity diagnostics.

### Changed

- Extended GitHub Actions validation to the development branch.


### Validation

- **358 automated tests passed.**
- **92.15% GitHub Actions coverage** / **92.21% local coverage** (macOS, Python 3.14).
- Minimum required coverage: **80%**.
- CI checks passed, including Ruff, mypy and pytest.

### Notes

- This is a beta release focused on FlexC connection reliability and protocol diagnostics.
- Session identity changes are logged for investigation but do not cause frame rejection.
- Fixed AES-256 encryption remains the supported configuration. Automatic encryption and key rotation are not yet validated; `KEY_UPDATE` (`0x40`) and `KEY_ACK` (`0x41`) support has not been implemented.
- No changes to alarm arming logic or existing entity behavior are intended.
- Hardware validation is recommended before production use.

---

## [1.1.4] - 2026-10-21

### Fixed

- Apply validated FlexC zone input events `2100` (active) and `2101` (restore) immediately to PIR, `entry_exit` and `entry_exit_2` zones, with protection against older in-flight polls.
- Prevent duplicate synthetic motion pulses when a live FlexC event already reported the same activation.
- Convert global panel arm/disarm connection and FLEXML failures to Home Assistant errors, including prechecks, as requested during HACS review.
- Preserve previously known area history attributes when a reconnect response omits them, without masking explicitly returned values.

### Changed

- Separate event-triggered POLL context resynchronization waits from actual zone read and lock timing.
- Move high-volume PIR, zone EVENT and FlexC context diagnostic messages from INFO to DEBUG.

### Added

- Optional, disabled-by-default **Last FlexC event ID** diagnostic sensor with the 20 most recent numeric event, zone and area IDs for investigating additional SPC devices without enabling global DEBUG logs.
- Regression tests for global alarm connection failures, precheck errors and the diagnostic sensor.

### Validation

- SPC4300 live testing: PIR event and restoration updates without duplicate activations.
- Independent tester: 28/28 PIR detections and restorations, no merged detections, no timeout or reconnect during the test; median detection 0.63 s ahead of Acre/MQTT.
- 349 automated Python tests passed locally; **92.00% GitHub CI coverage** and **92.06% local coverage** (Python 3.14). Ruff formatting/lint and mypy checks passed locally; HACS and Hassfest checks passed.

**Full Changelog**: https://github.com/minimicro34/ha-spc-flexc/compare/v1.1.3...v1.1.4

---

## [1.1.3] - 2026-10-19

### Fixed

- Avoided blocking timezone loading in Home Assistant's async execution path.
- Ensured FlexC event listeners are cleaned up when the initial coordinator refresh fails.
- Improved handling of failures raised by Home Assistant entity actions.
- Removed potentially sensitive raw `faults.last_event` data from downloadable diagnostics while retaining other fault indicators.
- Fixed the bundled card's detector **Restore** button layout so its label fits without overflowing.

### Changed

- Updated the bundled **SPC FlexC Card to v1.0.19**.

### Validation

- Home Assistant SPC4300 live testing validated reload/restart, connection, zone inhibition/isolation, garage arming, timezone and last-disarm state during the 1.1.3 beta cycle.
- Beta2 diagnostics confirmed `faults.last_event` is absent and no integration issues were reported.
- 319 automated Python tests passed with **91.71% CI coverage** during beta validation.
- Bundled card v1.0.19 passed frontend build and distribution consistency checks. Visual verification of the Restore button remains pending.

**Full Changelog**: https://github.com/minimicro34/ha-spc-flexc/compare/v1.1.2...v1.1.3

---

## [1.1.2] - 2026-10-19

### Added

- Bundled **SPC FlexC Card v1.0.18** in the integration repository, including canonical JavaScript sources, Node.js build scripts and the generated Lovelace module.
- Automatic registration of the bundled card as a Lovelace resource in storage mode, with migration of a single legacy standalone HACS card resource; YAML-managed resource instructions are documented.
- Latched intrusion **triggered** state on area and aggregate alarm entities for validated SPC intrusion events `1000` and `1001`, with triggering zone identifiers and names.
- Per-zone `intrusion_active` and `intrusion_triggered` attributes to distinguish current activity from a confirmed, latched alarm.
- Zone restoration button when SPC explicitly reports `RESTORE_ALLOWED=1`.
- Access-control door actions for temporary open, permanent open/free access, normal mode and forced lock, with door-mode verification.
- Area arm/disarm history and user display aliases, with Home Assistant options to customize user names.
- FlexC command trace diagnostics and regression tests covering command timeouts, session recovery, EVENT/POLL resynchronization and polling shutdown.

### Changed

- Improved command-timeout recovery by invalidating uncertain communication sessions and reconnecting with a fresh SPC handshake and POLL synchronization before further commands.
- Improved event-driven state handling and reconciliation with authoritative SPC status, including multi-panel and background-discovery behaviour.
- Improved door-mode verification and bounded recovery after uncertain communication outcomes.
- Updated integration and card documentation for the consolidated HACS distribution model.

### Fixed

- Corrected handling of intrusion states so entry-delay input activity alone does not mark an intrusion, while successive confirmed triggering zones are retained until confirmed disarming.
- Addressed event/poll synchronization and connection-lifecycle edge cases covered by the 1.1.2 regression suite.
- Incorporated the validated card v1.0.18 editor selection and horizontal-tab scrollbar fixes into the bundled frontend.

### Safety

- State-changing commands remain non-retriable after an uncertain timeout or connection failure.
- Zone restoration is exposed only when SPC reports the required capability.
- SPC panel state remains authoritative for alarm, zone and door status.

### Validation

- Extended beta-cycle testing on real SPC hardware and external tester installations.
- Added targeted tests for alarm history, user aliases, command tracing, EVENT/POLL reconciliation, door timeout recovery and zone restoration.
- Bundled frontend v1.0.18 was validated in Firefox, Chrome and Edge during its standalone development cycle.
- Home Assistant upgrade from the standalone HACS card was validated on a real installation: the Lovelace resource migrated automatically, the dashboard rendered correctly, several commands were tested successfully, and the standalone card was removed.
- Arm/disarm was not retested as part of the bundled-card migration; fresh installs and YAML-managed resource migration remain unverified.
- HACS, Hassfest and GitHub CI passed for beta25, with **309 automated tests** and **91.35% CI coverage**.

**Full Changelog**: https://github.com/minimicro34/ha-spc-flexc/compare/v1.1.1...v1.1.2

---

## [1.1.1] - 2026-09-19

### Fixed

- Fixed X-BUS tamper fault, inhibition and isolation state reconciliation for X-BUS devices reported by `CMD_STATUS_XBUS`.
- Renamed the X-BUS diagnostic entities to clearly separate `Tamper fault`, `Inhibition` and `Isolation`.

### Validated

Real SPC4300 hardware testing with a TYPE1 keypad validated:

- `INPUT=0002` / `0000` as the X-BUS keypad physical tamper fault state;
- `INHIBIT=0002` / `0000` as the X-BUS keypad tamper inhibition state;
- `ISOLATE=0002` / `0000` as the X-BUS keypad tamper isolation state;
- event `5314` / `5315` as immediate tamper inhibition / de-inhibition;
- event `5316` / `5317` as immediate tamper isolation / de-isolation;
- event-driven state changes are immediate, while periodic X-BUS polling reconciles the state if needed.

### Development

- Added regression coverage for X-BUS tamper status masks and event-driven inhibition/isolation state changes.
- Release validation passes 181 tests with 90.08% total coverage.

**Full Changelog**:
https://github.com/minimicro34/ha-spc-flexc/compare/v1.1.0...v1.1.1

---

## [1.1.0] - 2026-09-17

### Added

- Added dynamic discovery and Home Assistant representation of SPC X-BUS peripherals.
- Added validated X-BUS family mapping for SPC keypads, comfort keypads, SPCE650 I/O expanders, SPCE450 output expanders and SPCA210 door controllers.
- Added X-BUS auxiliary voltage/current and tamper diagnostics where reported by SPC.
- Added SPC zone inhibition and isolation controls with dedicated Home Assistant switches.
- Added Mapping Gate discovery, state monitoring and Home Assistant output switches.
- Added door status support and additional SPC device metadata.
- Added dynamic entity discovery when zones, X-BUS devices or Mapping Gates appear after initial setup.
- Added read retry handling for read-only FLEXML status requests.
- Added additional FlexC, ATS/ATP, panel and hardware diagnostics.

### Changed

- Reworked coordinator state discovery and refresh handling for areas, zones, doors, X-BUS devices and Mapping Gates.
- Improved FLEXML parsing and FlexC connection/message handling.
- Zone inhibition and isolation commands verify SPC capability fields before changing state and refresh the resulting SPC state after the command.
- Mapping Gate commands refresh and confirm the reported output state after a change.
- X-BUS entity presentation now exposes useful operational information while retaining lower-level fields in diagnostics.
- Expanded English and French translations for the new entities and controls.

### Safety

- State-changing FlexC commands remain deliberately non-retriable after an uncertain communication failure.
- Zone inhibition is only sent when SPC explicitly reports the corresponding inhibit/de-inhibit capability.
- Zone isolation is only sent when SPC explicitly reports the corresponding isolate/de-isolate capability.
- Mapping Gate state changes require a known discovered output and verify the resulting reported state.
- Read-only requests may use bounded retry/recovery handling without changing panel state.

### Validated

Real SPC hardware testing validated:

- zone `ACTION=0` — inhibit;
- zone `ACTION=1` — de-inhibit;
- zone `ACTION=2` — isolate;
- zone `ACTION=3` — de-isolate;
- `ISOLATED=1` as the canonical zone isolation state;
- `ISOLATE_ALLOWED=1` and `DEISOLATE_ALLOWED=1` as isolation capability fields;
- X-BUS TYPE1 keypad physical tamper, tamper inhibition and tamper isolation states;
- X-BUS peripheral identification for tested SPC keypad, comfort keypad, SPCE650, SPCE450 and SPCA210 hardware;
- Mapping Gate discovery, state monitoring and output control.

Some X-BUS fields remain hardware-dependent. Unknown or unvalidated protocol values are kept as diagnostics rather than assigned guessed semantics.

### Development

- Expanded automated coverage across integration setup/unload, FlexC connection and message handling, FLEXML parsing, coordinator updates, discovery, diagnostics, sensors, binary sensors, switches, Mapping Gates, X-BUS and zone controls.
- CI now runs coverage separately from the standard `make check` quality suite.
- Coverage threshold is enforced at 80% by `make coverage`.
- Release validation reached 90.03% total coverage.
- Updated contributor guidance to distinguish formatting, standard quality checks and coverage validation.

**Full Changelog**:
https://github.com/minimicro34/ha-spc-flexc/compare/v1.0.3...v1.1.0

---

## [1.0.3] - 2026-08-19

### Added

- Added real-time SPC area mode updates from unsolicited FlexC events.
- Added handling of validated SPC Full Set (`3504`) and Unset (`3501`) area events.

### Changed

- Area alarm entities now update immediately when the SPC reports a Set or Unset event.
- Global alarm state now follows real-time area state changes instead of waiting for the next coordinator refresh.
- Area updates continue to use SPC-reported events as the source of truth; no optimistic alarm state is introduced.

### Validated

Real SPC hardware testing validated:

- Full Set area event: `3504`;
- Unset area event: `3501`;
- area identification through `AREA_ID`;
- immediate individual area state updates;
- immediate global alarm state recalculation from updated area states.

### Development

- Added automated tests for SPC area Set / Unset FlexC events.

**Full Changelog**:
https://github.com/minimicro34/ha-spc-flexc/compare/v1.0.2...v1.0.3

---

## [1.0.2] - 2026-08-19

### Added

- Added real-time FlexC event handling for SPC panel 230 V mains faults.
- Added real-time FlexC event handling for SPC panel battery faults.
- Added real-time FlexC event handling for SPC panel enclosure tamper faults.
- Added real-time Engineer / Installer mode updates from unsolicited FlexC events.
- Added zone tamper fault and restoration handling from FlexC events.
- Added dynamic X-BUS device tamper diagnostics.
- Added X-BUS tamper isolation state tracking.
- Added active fault information when SPC refuses an arming operation with
  reason `2007`.
- Added automated tests for panel, zone and X-BUS FlexC event handling.

### Changed

- Panel fault entities now update from unsolicited FlexC events without waiting
  for the next coordinator refresh.
- Zone tamper state can now be updated directly from SPC FlexC events.
- SPC reason `2007` error reporting now includes known active panel faults when
  available.

### Diagnostics

- Added `230 V mains fault` diagnostic binary sensor.
- Added `Panel battery fault` diagnostic binary sensor.
- Added `Panel tamper` diagnostic binary sensor.
- Added dynamically discovered X-BUS tamper and tamper-isolation diagnostic
  entities.

### Validated

Real SPC hardware testing validated the following FlexC event pairs:

- Panel 230 V mains fault / restoration: `5000` / `5001`.
- Panel battery fault / restoration: `5006` / `5007`.
- Panel enclosure tamper fault / restoration: `5206` / `5207`.
- Zone tamper fault / restoration: `1008` / `1108`.
- X-BUS tamper fault event: `5312`.
- X-BUS tamper isolation / isolation restoration: `5316` / `5317`.
- X-BUS event `5317` is deliberately treated as restoration of the isolation
  state and does not clear the physical X-BUS tamper fault.

### Development

- Extended automated event handling and alarm-control tests.
- Test suite now contains 39 passing tests.

**Full Changelog**:
https://github.com/minimicro34/ha-spc-flexc/compare/v1.0.1...v1.0.2

---

## [1.0.1] - 2026-08-18

### Added

- Added a Home Assistant reconfiguration flow.
- SPC FlexC connection settings can now be changed directly from the Home
  Assistant UI without removing and recreating the integration.
- Existing configuration values are automatically pre-filled when opening the
  reconfiguration form.
- Added English and French translations for the reconfiguration flow.
- Added automated config flow tests.
- Added documentation for the separate SPC FlexC Lovelace dashboard card.
- Added native SPC FlexC branding for Home Assistant.

### Changed

- SPC address can now be changed from Home Assistant.
- FlexC TCP port can now be changed from Home Assistant.
- AES-256 encryption key can now be changed from Home Assistant.
- Command Profile username and password can now be changed from Home Assistant.
- Config entries now use the SPC panel serial number as their stable unique
  identifier instead of the panel IP address.
- Existing config entries using the SPC IP address as their unique identifier
  are automatically updated to the panel serial number after a successful
  panel refresh.

### Fixed

- Changing the SPC panel IP address no longer changes the logical identity of
  the SPC installation in Home Assistant.
- Duplicate SPC hosts are rejected during initial configuration and
  reconfiguration.

### Documentation

- Added Home Assistant reconfiguration instructions.
- Added a link to the separate `ha-spc-flexc-card` project.
- Documented the SPC FlexC Card as a HACS Dashboard repository.

### Alarm control

No changes were made to the validated alarm-control behaviour introduced in
v1.0.0.

Individual and global Full Set / Unset, arming prechecks, SPC reason decoding
and the no-automatic-retry safety behaviour remain unchanged.

**Full Changelog**:
https://github.com/minimicro34/ha-spc-flexc/compare/v1.0.0...v1.0.1

---

## [1.0.0] - 2026-08-18

🎉 **First stable release of SPC FlexC for Home Assistant.**

SPC FlexC provides native communication between compatible SPC alarm panels
and Home Assistant using the FlexC protocol, without requiring an additional
SPC gateway.

### Added

#### FlexC protocol

- Native FlexC receiver implemented directly in Home Assistant.
- AES-256 encrypted FlexC communication.
- FlexC connection handshake.
- Connection acknowledgement handling.
- FlexC polling and acknowledgement handling.
- Encrypted message processing.
- FLEXML command/reply transport.
- FlexC connection lifecycle management.
- Processing of unsolicited FlexC events.

#### Home Assistant integration

- Home Assistant UI configuration flow.
- Configuration of:
  - SPC address;
  - FlexC TCP port;
  - AES-256 encryption key;
  - Command Profile username;
  - Command Profile password.
- Coordinator-based SPC state management.
- Dynamic discovery of SPC areas.
- Dynamic discovery and monitoring of SPC zones.
- Home Assistant device grouping.
- English translations.
- French translations.
- HACS-compatible repository structure.

#### Alarm control

- Native Home Assistant `alarm_control_panel` entities for SPC areas.
- Global SPC alarm control panel.
- Individual area Unset / Disarm.
- Individual area Full Set / Arm Away.
- Part Set A / Arm Home when enabled by the SPC area.
- Part Set B / Arm Night when enabled by the SPC area.
- Global Full Set across discovered SPC areas.
- Global Unset across discovered SPC areas.
- SPC area mode mapping:
  - `MODE=0` — Unset / Disarmed;
  - `MODE=1` — Part Set A / Armed Home;
  - `MODE=2` — Part Set B / Armed Night;
  - `MODE=3` — Full Set / Armed Away.
- Area change-mode capability precheck before arming.
- Global precheck of all areas before the first global Full Set command is sent.
- Refresh of SPC state following mode-changing operations.

#### Arming error handling

- Human-readable Home Assistant errors when SPC refuses an arming operation.
- Automatic decoding of validated SPC not-ready reasons in the form `1000 + zone_id`.
- Automatic lookup of the blocking zone in coordinator zone data.
- Zone name and zone ID included in Home Assistant error messages.
- Safe fallback to `Zone <id>` when a zone name is unavailable.
- Dedicated handling of SPC reason `10006` for Engineer / Installer mode.
- Generic fallback for unknown SPC reason codes.
- English translated alarm-control exceptions.
- French translated alarm-control exceptions.

#### Global alarm safety

- All discovered areas are prechecked before global Full Set begins.
- Global Full Set is aborted before the first Set command if any area is known
  to be unable to arm.
- State-changing FlexC commands are deliberately never automatically retried.
- Global operation errors preserve visibility of incomplete operations.
- Individual area states remain available for verification after a global
  operation.

#### Area information

- Area ID.
- SPC operating mode.
- Human-readable mode name.
- Part Set A capability.
- Part Set B capability.
- Last Set timestamp where reported by SPC.
- Last Set user ID where reported by SPC.
- Last Set user name where reported by SPC.
- Last Unset timestamp where reported by SPC.
- Last Unset user ID where reported by SPC.
- Last Unset user name where reported by SPC.
- Last alarm information where reported by SPC.
- Internal bell state where reported by SPC.
- External bell state where reported by SPC.

#### Zones

- SPC zone discovery.
- Zone state monitoring.
- Zone metadata used for area arming error resolution.
- Live zone updates from supported FlexC events.

#### Diagnostics

- SPC panel diagnostic information.
- Panel summary processing.
- SPC alert status processing.
- FlexC ATS communication diagnostics.
- Support for diagnostic information reported by the panel.
- Graceful handling of optional diagnostic fields that are not available on
  every SPC installation.

#### Development

- Automated Python compilation checks.
- Ruff formatting checks.
- Ruff linting.
- Type checking.
- Automated tests.
- Hassfest validation.
- Repository-wide `make check` validation workflow.
- Contribution guidelines.
- Security guidance for real SPC panel testing.

### Safety

SPC FlexC v1.0 deliberately applies additional safeguards to alarm
state-changing commands.

#### No automatic command retry

A timeout does not guarantee that an SPC state-changing command was not
executed.

For this reason, commands such as Full Set and Unset are not automatically
resent after an uncertain communication failure.

This prevents a command from being executed twice because a reply was lost.

#### Individual arming precheck

Before sending an arming command, the integration asks the SPC panel whether
the requested mode change is currently allowed.

If SPC reports that the area is not ready, the state-changing command is not
sent.

#### Global arming precheck

Before global Full Set:

1. every discovered area is checked;
2. all prechecks must succeed;
3. only then are individual Full Set commands sent.

If any precheck fails, global arming stops before the first Set command.

### Validated

The v1.0 FlexC implementation has been validated against a real SPC
installation for:

- FlexC TCP connection;
- encrypted FlexC communication;
- connection handshake;
- polling;
- FLEXML request/reply handling;
- panel summary retrieval;
- alert status retrieval;
- area status retrieval;
- zone status retrieval;
- FlexC ATS status retrieval;
- individual area Full Set;
- individual area Unset;
- global Full Set;
- global Unset;
- resulting area state verification;
- refusal of arming when a zone is not ready;
- identification of the blocking zone from the SPC reason code;
- refusal of arming while Engineer / Installer mode is active;
- Home Assistant translated error reporting.

A complete real-panel Full Set / Unset cycle was validated using
`MODE 0 → MODE 3 → MODE 0`.

### Authentication

The validated v1.0 configuration uses an SPC FlexC Command Profile with
**Authentication mode: Command User Only**.

French SPC interfaces may display this as
**Utilisateur Commandes seulement**.

The Command Profile username and password are configured in Home Assistant and
used for FLEXML command authentication.

### Known limitations

#### Global Full Set is not atomic

The validated FlexC interface changes individual SPC areas.

Global Full Set is therefore implemented as coordinated individual area
operations rather than a single atomic all-areas SPC command.

All areas are prechecked first, but a communication failure or panel state
change after the prechecks can theoretically result in a partially completed
global operation.

State-changing commands are not automatically retried.

#### Command Profile user attribution

SPC can attribute FlexC Set/Unset operations authenticated through a Command
Profile to an internal Command Profile user.

The SPC event log may still identify the ATS / ATP Command Profile as the
technical origin, while user-related fields and native SMS notifications show
the internal Command Profile user.

This behaviour is generated by the SPC panel.

#### SPC User Only authentication

`SPC User Only / Utilisateur SPC seulement` authentication is not part of the
validated v1.0 configuration.

The supported and validated configuration for v1.0 is **Command User Only**.

#### Part Set support

Part Set A and Part Set B are only available when enabled and reported as
supported by the corresponding SPC area.

#### Hardware-dependent diagnostics

Diagnostic availability depends on:

- SPC panel model;
- firmware version;
- installed modules;
- communication configuration;
- optional hardware.

Not every SPC installation exposes every diagnostic field.

---

## Future development

Possible future improvements include:

- additional SPC diagnostic entities;
- additional FlexC event decoding;
- additional optional SPC hardware support;
- RF module diagnostics where exposed by SPC;
- modem diagnostics where exposed by SPC;
- additional FLEXML capabilities;
- enhanced Home Assistant alarm presentation;
- a dedicated SPC Lovelace card.

Safety rules introduced in v1.0 for state-changing commands will remain a core
design requirement for future alarm-control features.
