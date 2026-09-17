# SPC FlexC

> Native Siemens / Vanderbilt / Comelit SPC alarm integration for Home Assistant using the FlexC protocol.

<p align="center">

[![GitHub Release](https://img.shields.io/github/v/release/minimicro34/ha-spc-flexc)](https://github.com/minimicro34/ha-spc-flexc/releases)
[![CI](https://github.com/minimicro34/ha-spc-flexc/actions/workflows/ci.yml/badge.svg)](https://github.com/minimicro34/ha-spc-flexc/actions/workflows/ci.yml)
[![Hassfest](https://github.com/minimicro34/ha-spc-flexc/actions/workflows/hassfest.yml/badge.svg)](https://github.com/minimicro34/ha-spc-flexc/actions/workflows/hassfest.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-☕-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/minimicro34)
[![License](https://img.shields.io/github/license/minimicro34/ha-spc-flexc)](LICENSE)

</p>

<p align="center">
  🔐 Alarm control • 🏠 Areas • 🚪 Zones • 🔌 Outputs • 🧩 X-BUS • 📡 FlexC • 🩺 Diagnostics
</p>

---

SPC FlexC is a custom Home Assistant integration for compatible **Siemens / Vanderbilt / Comelit SPC alarm panels**.

It implements a native FlexC receiver directly inside Home Assistant. The SPC panel connects directly to Home Assistant through its FlexC communication path, allowing Home Assistant to retrieve panel information, monitor areas and zones, discover X-BUS hardware, receive events and control supported alarm and output functions without an additional SPC gateway.

> [!IMPORTANT]
> SPC FlexC can change the state of your alarm system.
>
> State-changing commands are deliberately never automatically retried after an uncertain communication failure. The integration also checks SPC-reported capabilities before sending supported alarm, inhibition and isolation commands.

---

## Contents

- [Features](#features)
- [Supported systems](#supported-systems)
- [Compatibility](#compatibility)
- [Requirements](#requirements)
- [Installation](#installation)
- [SPC configuration](#spc-configuration)
- [Home Assistant configuration](#home-assistant-configuration)
- [Reconfiguration](#reconfiguration)
- [Available entities](#available-entities)
- [SPC FlexC Card](#spc-flexc-card)
- [Alarm control](#alarm-control)
- [Zone inhibition and isolation](#zone-inhibition-and-isolation)
- [Mapping Gates / outputs](#mapping-gates--outputs)
- [X-BUS](#x-bus)
- [Diagnostics](#diagnostics)
- [Security recommendations](#security-recommendations)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [Support](#support)
- [License](#license)

---

## Features

### FlexC

- 📡 Native FlexC receiver implemented directly in Home Assistant
- 🔐 AES-256 encrypted FlexC communication
- 🔄 FlexC connection lifecycle management
- 💓 FlexC polling and acknowledgements
- 📥 FLEXML command/reply handling
- ⚡ Processing of unsolicited FlexC events
- 📶 FlexC ATS / ATP communication monitoring
- 🔁 Bounded recovery/retry handling for read-only status requests

### Alarm

- 🏠 Automatic SPC area discovery
- 🚪 Automatic SPC zone discovery
- 🔓 Individual area Unset / Disarm
- 🔒 Individual area Full Set / Arm Away
- 🏡 Part Set A / Arm Home when supported
- 🌙 Part Set B / Arm Night when supported
- 🛡️ Global Full Set and Global Unset
- ✅ SPC capability prechecks before mode-changing operations
- 🚫 Automatic arming refusal when an area is not ready
- 🚪 Identification of the zone preventing arming when reported by SPC
- 🛠️ Engineer / Installer mode detection
- ⚡ Live state updates from supported FlexC events

### Zones

- Live zone state monitoring
- Zone inhibition and de-inhibition controls when explicitly allowed by SPC
- Zone isolation and de-isolation controls when explicitly allowed by SPC
- Dynamic creation of supported Home Assistant control entities

### X-BUS

- Dynamic discovery of X-BUS peripherals reported by SPC
- Validated identification of tested SPC keypad, comfort keypad, SPCE650, SPCE450 and SPCA210 hardware
- Auxiliary voltage/current information where reported
- Tamper, tamper-inhibited and tamper-isolated diagnostics
- Device-specific metadata retained in Home Assistant diagnostics

### Outputs

- Mapping Gate discovery
- Mapping Gate state monitoring
- Home Assistant switch entities for discovered Mapping Gates
- Resulting output state verification after commands

### Home Assistant

- Native `alarm_control_panel` entities
- Zone, switch, sensor and binary sensor entities
- Dynamic entity discovery
- Home Assistant device grouping
- UI configuration and reconfiguration flows
- HACS-compatible repository structure
- English and French translations

---

## Supported systems

SPC FlexC is designed for SPC intrusion panels providing the FlexC protocol, including systems sold under the Siemens SPC, Vanderbilt SPC and Comelit SPC product families.

Actual feature availability depends on the panel model, firmware, installed modules, Command Profile permissions and SPC configuration.

---

## Compatibility

| Component | Supported |
| --- | --- |
| Home Assistant | ✅ |
| HACS | ✅ |
| SPC FlexC | ✅ |
| AES-256 FlexC encryption | ✅ |
| Areas | ✅ |
| Zones | ✅ |
| Full Set / Unset | ✅ |
| Global Full Set / Unset | ✅ |
| Part Set A / B | ✅ When enabled by the area |
| Zone inhibition | ✅ When allowed by SPC |
| Zone isolation | ✅ When allowed by SPC |
| Mapping Gates / outputs | ✅ |
| X-BUS discovery | ✅ |
| FlexC events | ✅ |
| Panel diagnostics | ✅ |
| FlexC ATS / ATP diagnostics | ✅ |

---

## Requirements

You need:

- Home Assistant;
- a compatible SPC panel with FlexC support;
- network connectivity between the SPC panel and Home Assistant;
- an available FlexC ATS / ATP configuration;
- an AES-256 FlexC encryption key;
- a dedicated SPC Command Profile;
- a command username and password.

Home Assistant must be reachable by the SPC panel on the configured FlexC TCP port. The port configured in the SPC ATP and Home Assistant must be identical. A typical port is `52000`, but another available TCP port may be used.

---

## Installation

### HACS

1. Open **HACS → Integrations**.
2. Open the **⋮** menu and select **Custom repositories**.
3. Add `https://github.com/minimicro34/ha-spc-flexc` as an **Integration** repository.
4. Install **SPC FlexC**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration → SPC FlexC**.

### Manual installation

Copy `custom_components/spc_flexc` to `/config/custom_components/spc_flexc` and restart Home Assistant.

---

## SPC configuration

### FlexC communication path

Configure an SPC ATS / ATP using FlexC. The SPC panel initiates the TCP connection to Home Assistant, which acts as the FlexC receiver.

Configure the ATP destination with:

- the Home Assistant IP address;
- the TCP port configured in SPC FlexC;
- FlexC encryption enabled;
- the same AES-256 encryption key configured in Home Assistant.

Make sure the destination is reachable, the TCP port is not blocked and the ATS / ATP is enabled.

### Command Profile

Create a dedicated SPC Command Profile. The configuration validated for this integration uses:

```text
Authentication mode: Command User Only
```

On a French SPC interface:

```text
Mode Authentification : Utilisateur Commandes seulement
```

Use dedicated command credentials and enable only the FLEXML permissions required by your installation.

Read permissions are required for the panel and hardware status used by the integration. Alarm control requires area change-mode permissions. Zone inhibition/isolation and Mapping Gate controls additionally require the corresponding commands to be permitted by the Command Profile.

> [!IMPORTANT]
> `SPC User Only / Utilisateur SPC seulement` has not been validated as the authentication mode for this integration.

---

## Home Assistant configuration

After installation, add **SPC FlexC** from **Settings → Devices & services**.

The configuration flow asks for:

- SPC address;
- FlexC TCP port;
- AES-256 key;
- Command Profile username;
- Command Profile password.

After setup, the SPC panel should establish its FlexC connection to Home Assistant.

---

## Reconfiguration

Connection settings can be changed without removing and recreating the integration.

Open **Settings → Devices & services → SPC FlexC → Reconfigure** to change the SPC address, FlexC TCP port, AES-256 key or Command Profile credentials.

After a successful panel refresh, the SPC panel serial number is used as the stable config-entry unique identifier. This allows the panel IP address to change without changing the logical identity of the SPC installation in Home Assistant.

---

## Available entities

The exact entities depend on the SPC panel, its configuration, capabilities and installed hardware.

### Alarm control panels

An `alarm_control_panel` entity is created for every discovered SPC area, together with a global SPC alarm control panel representing the complete installation.

### Zones

Discovered zones are represented in Home Assistant and are also used to resolve SPC arming refusal reasons. When SPC explicitly reports the relevant capabilities, dedicated switches are dynamically created for zone inhibition and isolation.

### Mapping Gates

Discovered Mapping Gates are represented as Home Assistant switches. Their friendly names are taken from SPC when available.

### X-BUS devices

X-BUS peripherals are dynamically grouped as Home Assistant devices. Tested device families can be identified as SPC keypads, comfort keypads, SPCE650 I/O expanders, SPCE450 output expanders and SPCA210 door controllers. Unknown hardware remains generic rather than being assigned guessed semantics.

### Diagnostics

Diagnostic entities are associated with the appropriate SPC devices and can include panel power/battery/tamper faults, modem/RF information, FlexC ATS/ATP state and X-BUS operational information.

Availability is hardware- and firmware-dependent.

---

## SPC FlexC Card

The companion **SPC FlexC Card** provides a dedicated Lovelace interface for the integration and is maintained as a separate project:

https://github.com/minimicro34/ha-spc-flexc-card

The backend integration and dashboard card are intentionally distributed separately so they can evolve independently.

For **screenshots, installation, dashboard configuration, responsive layout and the current visual feature set**, see the README of the SPC FlexC Card repository. Screenshots are intentionally not duplicated here.

The card can be installed through HACS as a custom repository of type **Dashboard**.

---

## Alarm control

SPC FlexC maps the validated SPC area modes as follows:

| SPC mode | SPC meaning | Home Assistant |
| ---: | --- | --- |
| `0` | Unset | Disarmed |
| `1` | Part Set A | Armed Home |
| `2` | Part Set B | Armed Night |
| `3` | Full Set | Armed Away |

Part Set controls are only exposed when the corresponding capability is reported by SPC.

### Global alarm control

Before Global Full Set, every discovered area is prechecked. If any precheck fails, the operation is aborted before the first Full Set command is sent. Only after all prechecks succeed are individual area commands sent.

Global Full Set is therefore coordinated but not atomic. A communication failure or panel state change after prechecks can still produce a partially completed operation. State-changing commands are not automatically retried.

### Arming errors

Validated SPC reasons in the form `1000 + zone_id` identify a zone preventing arming. The integration resolves the zone ID against discovered zones and reports it in the Home Assistant error when possible.

SPC reason `10006` is handled as Engineer / Installer mode preventing the requested arming operation. SPC reason `2007` is handled as an active system fault and known active diagnostic faults are included when available.

Unknown reason codes are preserved and are not assigned guessed meanings.

---

## Zone inhibition and isolation

SPC FlexC exposes zone inhibition and isolation controls only when the SPC panel explicitly reports the corresponding capability.

Real-panel testing validated:

| Action | Meaning |
| ---: | --- |
| `0` | Inhibit |
| `1` | De-inhibit |
| `2` | Isolate |
| `3` | De-isolate |

`ISOLATED=1` is used as the canonical reported zone isolation state. `ISOLATE_ALLOWED=1` and `DEISOLATE_ALLOWED=1` are used as the corresponding capability fields.

The integration does not infer permission from unrelated status values. If the expected capability is not explicitly reported, the state-changing command is not sent.

---

## Mapping Gates / outputs

SPC Mapping Gates discovered through FLEXML are exposed as Home Assistant switches.

The integration:

1. discovers the available Mapping Gates;
2. tracks their reported state;
3. sends the requested state change;
4. refreshes Mapping Gate status;
5. confirms the resulting state reported by SPC.

A command is rejected when the Mapping Gate is unknown or the requested state cannot be confirmed.

---

## X-BUS

SPC FlexC dynamically discovers X-BUS peripherals reported by the panel.

Validated mappings currently include:

- SPC keypad;
- SPC comfort keypad;
- SPCE650 I/O expander;
- SPCE450 output expander;
- SPCA210 door controller.

Operational entities can include auxiliary voltage/current and tamper-related states. Lower-level hardware identifiers and raw protocol values remain available in diagnostics where useful.

Unknown or unvalidated values are deliberately not given speculative meanings.

X-BUS control is not exposed unless the corresponding write semantics have been validated.

---

## Diagnostics

Depending on the panel, firmware and installed hardware, SPC FlexC can expose information related to:

- panel identity and firmware;
- panel operating state and summary;
- 230 V mains, battery and enclosure tamper faults;
- modem and RF information where reported;
- area information and last Set/Unset data;
- FlexC ATS / ATP communication state;
- X-BUS peripheral identity and status;
- X-BUS auxiliary power values;
- X-BUS tamper, tamper-inhibited and tamper-isolated states;
- raw protocol metadata retained for troubleshooting.

Some states are updated immediately from unsolicited FlexC events. Missing optional fields are tolerated because not every SPC installation exposes the same diagnostics.

---

## SPC command attribution

When FLEXML commands use **Command User Only** authentication, SPC can attribute Set/Unset operations to its internal Command Profile user. The SPC event log may still identify the ATS / ATP and Command Profile as the technical origin.

This behaviour is generated by the SPC panel and is not a Home Assistant user mapping.

---

## Security recommendations

SPC FlexC controls security equipment. Use a dedicated FlexC AES-256 key, a dedicated Command Profile, unique command credentials and only the permissions required by the integration. Restrict network access to the FlexC listener and keep another method of controlling the alarm available.

Never publish FlexC encryption keys, Command Profile passwords, SPC user PINs or installer codes in issues, logs, diagnostics or screenshots.

Do not expose the FlexC listener directly to the Internet.

---

## Known limitations

### Global Full Set is not atomic

Global Full Set coordinates individual area operations. All areas are prechecked first, but a later communication failure or panel state change can still result in an incomplete operation. State-changing commands are never automatically retried after an uncertain result.

### Hardware-dependent diagnostics

Entity and diagnostic availability depends on panel model, firmware, installed modules and configuration.

### X-BUS topology

X-BUS discovery reflects the peripherals returned by the SPC FlexC/FLEXML interface. If a panel does not return a peripheral in the available status data, Home Assistant cannot represent it from that response.

### Unvalidated protocol fields

Unknown values are retained for diagnostics rather than assigned guessed semantics. Additional hardware and write operations are added only when their behaviour is sufficiently validated.

---

## Troubleshooting

### SPC does not connect

Check the Home Assistant destination configured in the SPC ATP, FlexC TCP port, firewall rules, ATS / ATP enabled state, AES-256 configuration and network connectivity. Remember that the SPC panel initiates the connection to Home Assistant.

### FlexC connects but FLEXML commands fail

Check the Command Profile authentication mode, command username/password and command permissions.

### Arming fails

Use the Home Assistant error message and individual area/zone states. If a blocking zone or SPC reason is reported, correct the panel condition before retrying.

### Dynamic hardware is missing

Check Home Assistant diagnostics and the raw SPC/FLEXML data first. Hardware-dependent entities can only be created for objects actually returned by SPC.

---

## Development

Development instructions are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

The main validation commands are:

```bash
make format
make check
make coverage
```

`make format` applies Ruff formatting.

`make check` runs compilation, formatting verification, linting, type checking and the test suite. It **does not** run the coverage gate.

`make coverage` runs the tests with pytest-cov and enforces the repository minimum coverage threshold.

Before a pull request or release, run both:

```bash
make check
make coverage
git diff --check
```

The current coverage gate is 80%. The v1.1.0 release validation reached 90.03% total coverage.

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

Useful contributions include bug fixes, additional SPC hardware validation, diagnostics, FlexC/FLEXML support, event decoding, tests, translations and documentation.

For protocol semantics, prefer real-panel evidence or reliable documentation. Do not assign meanings to unknown fields solely from names or observed numeric coincidences.

> [!WARNING]
> Never publish FlexC encryption keys, Command Profile passwords, SPC user PINs, installer codes or other alarm credentials.

---

## Disclaimer

SPC FlexC is an independent open-source project. It is not affiliated with, endorsed by, or supported by Siemens, Vanderbilt, Comelit or Home Assistant.

Alarm systems are security equipment. Always validate the behaviour of your specific panel and installation before relying on remote alarm control.

The authors and contributors cannot be held responsible for alarm activations, failed arming operations, missed events or other consequences resulting from use of this integration.

---

## Support

If you find SPC FlexC useful and would like to support its development, you can buy me a coffee.

<p align="center">
  <a href="https://buymeacoffee.com/minimicro34">
    <img
      src="https://github.com/appcraftstudio/buymeacoffee/raw/master/Images/snapshot-bmc-button.png"
      alt="Buy Me a Coffee"
      width="300"
    />
  </a>
</p>

Bug reports, feature suggestions, contributions and GitHub stars are also appreciated. Please use GitHub Issues for bug reports and feature requests and include the panel model, firmware, integration version, Home Assistant version, relevant logs and diagnostics when possible — without credentials or encryption keys.

---

## License

Copyright © 2026 minimicro34.

This project is licensed under the [GNU General Public License v3.0 or later](LICENSE).
