# Changelog

All notable changes to SPC FlexC are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.5] - Unreleased

### Fixed

- Render a proper shield-alert icon and explicit Sabotage state for tampered detectors, fixing an empty icon caused by returning an object instead of an icon name.
- Retry incomplete or failed Home Assistant entity-registry discovery after a short cooldown instead of leaving detector/output scope permanently empty after a transient failure.
- Include tamper event flags from ordinary detectors in each area’s sabotage indicator, not only dedicated tamper entities.
- Keep the selected Outputs tab while SPC entity scope is loading and distinguish loading from a confirmed empty detector list.
- Echo the panel-provided SPC account code in legacy FlexC CONNECT acknowledgements (`0x01`) instead of a hardcoded value.
- Clear pending commands when a new TCP session replaces the previous one, preventing stale command timeouts and buffered frames from interfering with the new session.
- Apply a 60-second idle read timeout to close inactive or stalled FlexC TCP sessions.
- Distinguish SPC authentication error `54` from other panel error codes.
- Preserve per-zone tamper/trouble observations across ordinary PIR input polling instead of clearing an acknowledged/latched diagnostic from a motion/rest transition.
- Keep startup-only slow PIR zone polling measurements at DEBUG for the first 30 seconds after zone polling begins; preserve WARNING-level reporting afterwards without delaying or changing polling.

### Added

- Display recent FlexC events in a rounded, collapsible System-tab panel with an event count.
- Group wireless event observations in an expandable section and show RF diagnostics, including RF Jamming when `off`, under Wireless (RF).
- Non-blocking, per-session diagnostics for SPC account code, connection ID and receiver identifier changes, with warnings deduplicated per field.
- Sanitized identity samples for incoming CONNECT, POLL, EVENT and DATA messages, once per message type and TCP session.
- Explicit diagnostic detection of `KEY_UPDATE (0x40)` and `KEY_ACK (0x41)` messages.
- Extend the optional, disabled-by-default **Last FlexC event ID** diagnostic sensor with decoded alarm type and transition for validated panic, medical, fire and hold-up events from user commands, wireless keypads and X-BUS keypads.
- Include validated event origin and identifiers in the diagnostic event history, including events without an area or zone identifier.
- Add Node.js regression checks for the bundled SPC FlexC Lovelace card and include `make card-test` in `make check`, covering panel selection, diagnostic scoping, HTML escaping, missing entities, and alarm-state presentation.
- Add two diagnostic binary sensors per discovered SPC zone for tamper and trouble, independent of the physical detector state, with support for zone-type event families `1200–1223` / `1300–1323` and `1800–1823` / `1900–1923`.
- Decode zone input events `2100`, `2101`, `2103`, `2107` and zone-type tamper/trouble transitions in the optional **Last FlexC event ID** diagnostic sensor; keep numeric IDs, area/zone identifiers and event classifications in the recent-event attributes.
- Show tamper/trouble labels on detector rows and counters in collapsed detector groups and the general card overview, without replacing the detector's original icon or counting anomalies as additional detectors.
- Display recent FlexC event diagnostics in the card's **System** tab when the optional event-ID sensor is enabled; preserve existing Wireless and X-BUS diagnostics.

### Changed

- Move RF Jamming out of the separate RF diagnostics list to avoid duplicate display in the System tab.
- Preserve diagnostic panel expansion state across Home Assistant card updates and synchronize the bundled Lovelace JavaScript.
- Learn the active connection ID from the first `POLL (0x20)` instead of assuming a fixed receiver connection ID; treat the known receiver identifier `0x77359401` as informational during connection setup.
- Avoid misleading identity-change warnings during the initial CONNECT-to-POLL transition while retaining warnings for unexpected changes after the session baseline is established.
- Keep identity diagnostics non-blocking: valid incoming frames are accepted even when identifiers differ.
- Document the bundled card test workflow and clarify that diagnostic alarm event classifications are historical observations, not persistent alarm states.
- Bundle **SPC FlexC Card v1.0.21** with integration **v1.1.5-beta.5**, including updated event history and zone-alert presentation.

### Safety and limitations

- Transient alarm events do not latch Home Assistant alarm state without an authoritative SPC state transition; missing area IDs do not suppress event diagnostics.
- Zone tamper/trouble diagnostics follow observed zone events; unknown zone IDs (including events described as **Unused Zone**) do not create additional entities. Diagnostic event history is in-memory and resets on integration reload.
- AES key rotation is **not implemented**: `KEY_UPDATE` and `KEY_ACK` remain diagnostic-only; no key change or outgoing key acknowledgement is performed.
- No changes to outbound FlexC command handling or AES encryption are intended by the session identity diagnostics.

### Validation

- Frontend distribution consistency check passed in GitHub Actions for the beta.6 development changes; live Home Assistant UI verification remains pending.
- Regression tests cover legacy CONNECT variants, session replacement, idle timeout, authentication errors, per-message identity samples and session identity changes, plus zone-type tamper/trouble event transitions and decoded event descriptions.
- **427 Python tests passed** and **18 Node.js card tests passed** locally and in GitHub Actions on the validated beta.5 development code before the version/documentation update.
- **Python coverage: 91.95% on GitHub Actions / 92.01% locally**.
- Local tests and GitHub Actions passed before the beta.5 version/documentation update. Final CI verification of the packaged version and hardware/UI validation remain to be confirmed before the stable release.

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
