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
  🔐 Alarm control • 🏠 Areas • 🚪 Zones • 📡 FlexC • 🩺 Diagnostics
</p>

---

SPC FlexC is a custom Home Assistant integration for compatible
**Siemens / Vanderbilt / Comelit SPC alarm panels**.

It implements a native FlexC receiver directly inside Home Assistant.

The SPC panel connects directly to Home Assistant using its FlexC communication
path, allowing Home Assistant to retrieve panel information, monitor areas and
zones, receive events and control the alarm system without requiring an
additional SPC gateway.

> [!IMPORTANT]
> SPC FlexC can arm and disarm your alarm system.
>
> State-changing commands are deliberately never automatically retried.
> Before arming, the integration asks the SPC panel whether the requested mode
> change is currently allowed.

---

## Contents

- [Features](#features)
- [Supported systems](#supported-systems)
- [Compatibility](#compatibility)
- [Requirements](#requirements)
- [Installation](#installation)
- [SPC configuration](#spc-configuration)
- [Home Assistant configuration](#home-assistant-configuration)
- [Available entities](#available-entities)
- [Alarm control](#alarm-control)
- [Global alarm control](#global-alarm-control)
- [Arming safety and error reporting](#arming-safety-and-error-reporting)
- [Diagnostics](#diagnostics)
- [SPC command attribution](#spc-command-attribution)
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
- 🔄 FlexC connection management
- 💓 FlexC polling and acknowledgements
- 📥 FLEXML command/reply handling
- ⚡ Processing of unsolicited FlexC events
- 📶 FlexC ATS communication monitoring

### Alarm

- 🏠 Automatic SPC area discovery
- 🚪 Automatic SPC zone discovery
- 🔓 Individual area Unset / Disarm
- 🔒 Individual area Full Set / Arm Away
- 🏡 Part Set A / Arm Home when supported
- 🌙 Part Set B / Arm Night when supported
- 🛡️ Global Full Set
- 🔓 Global Unset
- ✅ Precheck before mode-changing operations
- 🚫 Automatic arming refusal when an area is not ready
- 🚪 Identification of the zone preventing arming
- 🛠️ Engineer / Installer mode detection
- 🌐 English and French error messages

### Home Assistant

- 🏠 Native `alarm_control_panel` entities
- 🚪 SPC zone entities
- 🩺 Diagnostic entities
- 🔄 UI configuration flow
- ⚡ Live updates from FlexC events
- 📦 HACS compatible
- 🌐 English and French translations

### Safety

- 🛡️ State-changing FlexC commands are never automatically retried
- 🔍 Individual arming operations are prechecked with the SPC panel
- 🔍 Every area is prechecked before global arming starts
- 🚫 Global arming is cancelled before the first Set command if an area is
  already known to be unable to arm
- 📥 Resulting states are refreshed from the SPC panel after commands

---

## Supported systems

SPC FlexC is designed for SPC intrusion panels providing the FlexC protocol,
including systems sold under the:

- Siemens SPC
- Vanderbilt SPC
- Comelit SPC

product families.

Actual feature availability depends on the panel model, firmware, installed
modules and SPC configuration.

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
| Part Set A | ✅ When enabled by the area |
| Part Set B | ✅ When enabled by the area |
| FlexC events | ✅ |
| Panel diagnostics | ✅ |
| FlexC ATS diagnostics | ✅ |

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

Home Assistant must be reachable by the SPC panel on the configured FlexC TCP
port.

The port used by your SPC ATP and Home Assistant must be identical.

A typical port is:

```text
52000
```

You may use another available TCP port.

---

## Installation

### HACS

1. Open **HACS**.
2. Go to **Integrations**.
3. Open the **⋮** menu.
4. Select **Custom repositories**.
5. Add:

```text
https://github.com/minimicro34/ha-spc-flexc
```

Select the category:

```text
Integration
```

6. Install **SPC FlexC**.
7. Restart Home Assistant.

Then go to:

**Settings → Devices & services → Add integration → SPC FlexC**

### Manual installation

Copy:

```text
custom_components/spc_flexc
```

to:

```text
/config/custom_components/spc_flexc
```

Restart Home Assistant.

---

## SPC configuration

### FlexC communication path

Configure an SPC ATS / ATP using FlexC.

The SPC panel initiates the TCP connection to Home Assistant.

Home Assistant therefore acts as the FlexC receiver.

Configure the ATP destination with:

- the IP address of Home Assistant;
- the TCP port configured in SPC FlexC;
- FlexC encryption enabled;
- the AES-256 encryption key used by Home Assistant.

Make sure that:

- the Home Assistant IP address is reachable from the SPC panel;
- the configured TCP port is not blocked by a firewall;
- no other receiver is listening for the same SPC FlexC destination;
- the ATS / ATP is enabled.

### AES-256 encryption

Configure the FlexC ATP to use AES-256 encryption.

The same encryption key must be configured in Home Assistant.

Keep this key private.

### Command Profile

Create a dedicated SPC Command Profile.

For example:

```text
Name: Home Assistant
```

Use:

```text
Authentication mode: Command User Only
```

or, on a French SPC interface:

```text
Mode Authentification : Utilisateur Commandes seulement
```

Create dedicated command credentials, for example:

```text
Command username: homeassistant
Command password: <strong unique password>
```

Enter these same credentials in the SPC FlexC Home Assistant integration.

> [!IMPORTANT]
> **Command User Only / Utilisateur Commandes seulement** is the authentication
> mode validated for SPC FlexC v1.0.
>
> `SPC User Only / Utilisateur SPC seulement` is not part of the validated
> v1.0 configuration.

### Command permissions

The Command Profile must allow the FLEXML commands required by the integration.

This includes commands required to retrieve:

- panel summary;
- alert status;
- area status;
- zone status;
- FlexC / ATS status where available.

Alarm control additionally requires permission for:

- area change-mode status;
- area mode changes.

Only enable the permissions required by your installation.

A dedicated Command Profile is recommended instead of reusing an installer or
personal SPC account.

---

## Home Assistant configuration

After installing and restarting Home Assistant:

1. Open **Settings**.
2. Open **Devices & services**.
3. Select **Add integration**.
4. Search for **SPC FlexC**.

The integration asks for the following settings.

### SPC address

The IP address of the SPC panel.

Example:

```text
192.168.1.200
```

### FlexC port

The TCP port on which Home Assistant listens for the SPC FlexC connection.

Example:

```text
52000
```

### AES-256 key

The FlexC encryption key configured in the SPC ATP.

The same key must be configured on both sides.

### Command username

The username configured in the SPC Command Profile.

Example:

```text
homeassistant
```

### Command password

The password configured for the SPC Command Profile.

After setup, the SPC panel should establish its FlexC connection to Home
Assistant.

---

## Available entities

The exact entities depend on the SPC panel, its configuration and the installed
hardware.

### Alarm control panels

An alarm control panel entity is created for every discovered SPC area.

Examples may include:

```text
alarm_control_panel.logis
alarm_control_panel.garage
```

The actual entity IDs are generated by Home Assistant from the discovered area
names.

A global SPC alarm control panel is also created to control all discovered
areas together.

### Zones

SPC zones discovered by the integration are exposed in Home Assistant.

Zone information is also used internally to provide meaningful arming errors.

For example, if SPC reports that zone ID `2` prevents an area from being armed,
the integration can resolve that ID to the corresponding zone name.

### Diagnostics

Diagnostic entities are associated with the appropriate SPC devices and expose
information reported by the panel and FlexC communication path.

The exact diagnostic entities available depend on what the panel reports.

---

## Alarm control

SPC FlexC maps the validated SPC area modes to Home Assistant as follows:

| SPC mode | SPC meaning | Home Assistant |
| ---: | --- | --- |
| `0` | Unset | Disarmed |
| `1` | Part Set A | Armed Home |
| `2` | Part Set B | Armed Night |
| `3` | Full Set | Armed Away |

### Disarm

Home Assistant:

```text
Disarm
```

SPC:

```text
MODE=0
```

### Arm Away

Home Assistant:

```text
Arm Away
```

SPC:

```text
MODE=3
```

This performs a Full Set of the selected SPC area.

### Arm Home

When Part Set A is enabled for the area:

```text
Arm Home
```

maps to:

```text
MODE=1
```

### Arm Night

When Part Set B is enabled for the area:

```text
Arm Night
```

maps to:

```text
MODE=2
```

Part Set controls are only exposed when the SPC area reports that the
corresponding Part Set mode is enabled.

---

## Global alarm control

SPC FlexC also creates a global alarm control panel representing the complete
SPC installation.

It provides:

- **Arm Away** — Full Set all discovered areas;
- **Disarm** — Unset all discovered areas.

### Global Full Set

Global Full Set is deliberately implemented in two phases.

First, the integration asks SPC whether **every discovered area** can change to
Full Set.

Conceptually:

```text
Area 1 precheck
Area 2 precheck
...
```

If any area fails its precheck, the global operation is aborted before the
first Full Set command is sent.

Only after all prechecks succeed does the integration send the individual area
mode-change commands.

This prevents a known not-ready area from causing an avoidable partial arming
operation.

### Global Unset

Global Unset sends an Unset request to the applicable areas.

If an individual operation fails, the integration reports the incomplete
global operation.

State-changing commands are not automatically retried.

### Global state

The global alarm entity reflects the combined state of the SPC areas.

When all areas are Unset, the global entity is disarmed.

When all relevant areas are Full Set, the global entity is armed away.

If areas have different modes, the global entity can report a mixed/unknown
state while the individual area entities continue to expose their exact
states.

---

## Arming safety and error reporting

Before changing an area to an armed mode, SPC FlexC performs a read-only
change-mode capability request.

This allows the SPC panel itself to decide whether the requested operation is
currently permitted.

### Zone preventing arming

Validated SPC reason codes in the form:

```text
1000 + zone_id
```

identify a zone preventing the requested arming operation.

For example:

```text
reason 1002
```

means:

```text
zone_id = 2
```

SPC FlexC looks up the zone in the zones already discovered by the coordinator.

Home Assistant can therefore display an error such as:

```text
Cannot arm Logis: zone Salon (ID 2) is not ready (SPC reason 1002).
```

With Home Assistant configured in French, the translated message is displayed.

If the zone exists but has no usable name, SPC FlexC uses a fallback such as:

```text
Zone 2
```

### Engineer / Installer mode

The validated SPC reason:

```text
10006
```

is handled separately.

It indicates that Engineer / Installer mode prevents the requested arming
operation.

Home Assistant displays a dedicated error instead of attempting the Set
command.

### Unknown SPC reasons

Unknown reason codes are not guessed.

SPC FlexC preserves the original SPC reason and displays a generic translated
error.

This makes unexpected panel responses visible without assigning an incorrect
meaning to undocumented codes.

---

## Diagnostics

SPC FlexC retrieves diagnostic information directly from the SPC panel and the
FlexC communication path.

Depending on the panel, firmware and installed hardware, this can include
information related to:

- panel identity;
- firmware information;
- panel operating state;
- panel summary;
- power-related status reported by SPC;
- voltage/current-related values reported by SPC;
- alert state;
- FlexC ATS status;
- communication path status.

Not every SPC installation exposes the same diagnostic information.

Optional hardware and firmware differences can therefore cause some values or
entities to be unavailable.

The integration is designed to tolerate missing optional diagnostic fields.

### Area information

Area entities can expose SPC-specific information such as:

- area ID;
- current SPC mode;
- mode name;
- Part Set A availability;
- Part Set B availability;
- last Set time;
- last Set user ID;
- last Set user name;
- last Unset time;
- last Unset user ID;
- last Unset user name;
- last alarm information;
- internal bell state;
- external bell state.

---

## SPC command attribution

When FLEXML commands are authenticated using:

```text
Command User Only
```

SPC can attribute Set/Unset operations to its internal Command Profile user.

For example, SPC may report a user similar to:

```text
User 9995
Command Profile User
```

even when the FlexC Command Profile itself is named:

```text
Home Assistant
```

The SPC event log can still identify the technical origin of the command
through the ATS / ATP and Command Profile.

This behaviour is generated by the SPC panel and is not a Home Assistant user
mapping.

It can also affect the user name shown in native SPC SMS notifications for
remote Set/Unset operations.

---

## Security recommendations

SPC FlexC controls a security system.

Use a dedicated configuration for Home Assistant.

Recommended:

- use a dedicated FlexC AES-256 encryption key;
- use a dedicated SPC Command Profile;
- use a unique command username;
- use a strong unique command password;
- enable only the FLEXML commands required by the integration;
- restrict network access to the FlexC listener;
- keep Home Assistant and the SPC panel on trusted networks;
- keep Home Assistant backups;
- keep another method of controlling the alarm available.

Do not:

- expose the FlexC listener directly to the Internet;
- publish your AES-256 key;
- publish the Command Profile password;
- publish SPC user PINs or installer codes;
- reuse sensitive credentials unnecessarily.

---

## Known limitations

### Global Full Set is not atomic

The validated FlexC interface changes the mode of individual areas.

Global Full Set therefore works by:

1. prechecking every area;
2. aborting before arming if any precheck fails;
3. sending individual Full Set commands after all prechecks succeed.

There is still a theoretical window where an area may successfully arm and a
later command may fail because:

- the FlexC connection is interrupted;
- the panel state changes after the precheck;
- another condition prevents a later operation.

For safety, SPC FlexC does **not** automatically retry state-changing commands.

Always inspect the resulting area states if Home Assistant reports an
incomplete global operation.

### Command Profile attribution

SPC may record FlexC Set/Unset operations using its internal Command Profile
user rather than the friendly Command Profile name in user-related event
fields and native SMS notifications.

### SPC User Only authentication

The validated v1.0 configuration uses:

```text
Command User Only
```

`SPC User Only / Utilisateur SPC seulement` is not supported as part of the
validated v1.0 configuration.

### Part Set availability

Part Set A and Part Set B depend on the configuration of each SPC area.

Home Assistant only exposes these controls when the corresponding capability
is reported by SPC.

### Hardware-dependent diagnostics

Some SPC diagnostic information depends on optional hardware, firmware and
communication modules.

Not every panel will expose every possible diagnostic value.

---

## Troubleshooting

### SPC does not connect

Check:

- Home Assistant IP address configured in the SPC ATP;
- FlexC TCP port;
- firewall rules;
- ATS / ATP enabled state;
- AES-256 configuration;
- network connectivity from SPC to Home Assistant.

Remember that the SPC panel initiates the connection to Home Assistant.

### FlexC connects but FLEXML commands fail

Check:

- Command Profile authentication mode is **Command User Only**;
- command username;
- command password;
- Command Profile command permissions.

### `GET_PANEL_SUMMARY` fails

Verify that the Command Profile is configured using the validated
authentication mode:

```text
Command User Only
```

and that the required read commands are enabled in its command filter.

### Arming fails with a zone error

Home Assistant should identify the zone preventing arming.

Restore or close the reported zone and retry the operation.

Example:

```text
Cannot arm Logis: zone Salon (ID 2) is not ready (SPC reason 1002).
```

### Arming fails with reason 10006

Exit SPC Engineer / Installer mode before attempting to arm the system.

### Global arming fails

If the failure occurs during the precheck phase, no Full Set command should
have been sent.

Check the Home Assistant error message to identify the area or zone preventing
the operation.

If an error occurs after commands have started, inspect the individual area
entities to determine their actual SPC states.

---

## Development

Development instructions and contribution guidelines are available in
[CONTRIBUTING.md](CONTRIBUTING.md).

Common commands:

```bash
make compile
make format
make format-check
make lint
make typecheck
make test
make check
make clean
```

Before committing changes, run:

```bash
make check
```

The complete validation suite should pass.

It is also useful to check the Git diff for whitespace errors:

```bash
git diff --check
```

---

## Contributing

Contributions are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

Contributions can include:

- bug fixes;
- support for additional SPC hardware;
- additional diagnostics;
- additional FlexC/FLEXML support;
- event decoding improvements;
- tests;
- translations;
- documentation.

For significant FlexC protocol or alarm-control changes, please open a GitHub
Issue before starting a large implementation.

> [!WARNING]
> Never publish FlexC encryption keys, Command Profile passwords, SPC user
> PINs, installer codes or other alarm credentials in Issues, Pull Requests,
> logs or screenshots.

---

## Disclaimer

SPC FlexC is an independent open-source project.

It is not affiliated with, endorsed by, or supported by Siemens, Vanderbilt,
Comelit or Home Assistant.

Alarm systems are security equipment.

Always validate the behaviour of your specific panel and installation before
relying on remote alarm control.

The authors and contributors cannot be held responsible for alarm activations,
failed arming operations, missed events or other consequences resulting from
the use of this integration.

---

## Support

If you find SPC FlexC useful and would like to support its development, you can
buy me a coffee.

<p align="center">
  <a href="https://buymeacoffee.com/minimicro34">
    <img
      src="https://github.com/appcraftstudio/buymeacoffee/raw/master/Images/snapshot-bmc-button.png"
      alt="Buy Me a Coffee"
      width="300"
    />
  </a>
</p>

Your support helps dedicate more time to improving the integration, adding new
features, testing additional SPC functionality and fixing issues.

Bug reports, feature suggestions, contributions and GitHub stars are also
greatly appreciated.

Please use GitHub Issues for bug reports and feature requests.

When reporting an issue, please include whenever possible:

- SPC panel model;
- SPC firmware version;
- SPC FlexC integration version;
- Home Assistant version;
- a clear description of the problem;
- relevant Home Assistant logs;
- Home Assistant diagnostics.

For alarm-control problems, also include:

- the affected area;
- the requested mode;
- the current mode;
- the SPC reason code, if available.

Never include passwords, PINs or encryption keys.

---

## License

This project is licensed under the MIT License.

See [LICENSE](LICENSE) for details.