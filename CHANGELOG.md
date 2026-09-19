# Changelog

All notable changes to SPC FlexC are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.1] - 2026-09-19

### Fixed

- Fixed X-BUS tamper fault, inhibition and isolation state reconciliation for X-BUS devices reported by `CMD_STATUS_XBUS`.
- X-BUS keypad tamper inhibition now updates immediately from validated FlexC events `5314` / `5315`.
- X-BUS keypad tamper isolation continues to update immediately from validated FlexC events `5316` / `5317`, with periodic X-BUS status polling now correctly reconciling the same state.
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
