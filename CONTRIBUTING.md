# Contributing to SPC FlexC

Thank you for your interest in contributing to SPC FlexC.

SPC FlexC is a custom Home Assistant integration for Siemens / Vanderbilt /
Comelit SPC alarm panels using the native FlexC protocol.

Contributions are welcome, including:

- bug fixes;
- support for additional SPC panel models or firmware versions;
- additional FlexC diagnostics;
- improved event decoding;
- additional FLEXML command support;
- translations;
- documentation improvements;
- tests.

Because this integration communicates with a security system and can perform
state-changing operations such as arming and disarming, changes affecting
FlexC commands require particular care.

---

## Development setup

Clone the repository:

```bash
git clone https://github.com/minimicro34/ha-spc-flexc.git
cd ha-spc-flexc
```

Install the development dependencies required by the project.

The repository Makefile provides the standard development commands.

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

Before submitting a change, always run:

```bash
make check
```

All checks must pass.

---

## Code quality

Contributions should follow the conventions already used by the integration
and Home Assistant.

In particular:

- keep asynchronous operations non-blocking;
- use Home Assistant entity and coordinator patterns;
- keep typing annotations accurate;
- keep Ruff formatting and linting clean;
- avoid broad exception handlers such as `except Exception`;
- add or update tests when changing behaviour;
- preserve compatibility with the supported Home Assistant version.

Do not disable linting or typing rules merely to make a check pass.

Fix the underlying issue whenever possible.

---

## FlexC command safety

SPC FlexC controls a real alarm system.

Any contribution involving commands that change the panel state must follow
the safety rules below.

### Never automatically retry state-changing commands

Commands such as:

- Full Set;
- Unset;
- Part Set A;
- Part Set B;
- future output/control commands that can modify the SPC state;

must **never be automatically retried** after an uncertain timeout or
connection failure.

A timeout does not prove that the SPC panel did not execute the command.

Automatically sending the same command again could therefore cause an
unexpected second operation.

Read-only requests may use the normal connection recovery mechanisms where
appropriate.

### Precheck before arming

Area arming operations must use the SPC change-mode precheck before sending the
state-changing command.

For example:

```xml
<CMD_GET_AREA_CHANGE_MODE_STATUS AREA_ID="1" MODE="3" />
```

must be checked before:

```xml
<CMD_AREA_CHANGE_MODE AREA_ID="1" MODE="3" />
```

when performing a Full Set.

If the precheck reports that the area is not ready, the state-changing command
must not be sent.

### Global arming

Global Full Set is implemented as coordinated individual area commands.

Before sending the first Full Set command:

1. discover the relevant areas;
2. precheck every area;
3. abort the global operation if any precheck fails;
4. only begin sending state-changing commands after every precheck succeeds.

This reduces the risk of partially arming the installation because one area
was already known to be unavailable.

It cannot make the operation fully atomic: communication can still fail or
panel conditions can change after the prechecks.

### Verify resulting state

Whenever practical, refresh the SPC state after a command instead of assuming
that an accepted command means that the final requested state has already been
reached.

---

## SPC area modes

The currently validated SPC area mode mapping is:

| SPC mode | Meaning | Home Assistant |
|---:|---|---|
| `0` | Unset | Disarmed |
| `1` | Part Set A | Armed Home |
| `2` | Part Set B | Armed Night |
| `3` | Full Set | Armed Away |

Do not change this mapping based only on assumptions or undocumented examples.

Changes must be validated against an SPC panel or reliable protocol evidence.

---

## SPC change-mode errors

The integration decodes known SPC change-mode reasons.

### Zone not ready

Validated reason codes in the form:

```text
1000 + zone_id
```

identify the zone preventing the requested arming operation.

For example:

```text
1002
```

corresponds to:

```text
zone_id = 2
```

The integration should resolve the zone against the zones already known by the
coordinator and present both its name and ID to Home Assistant.

If a zone name is unavailable, use a safe fallback such as:

```text
Zone 2
```

### Engineer / Installer mode

The validated reason:

```text
10006
```

is handled separately as Engineer / Installer mode preventing the requested
operation.

### Unknown reasons

Do not invent meanings for unknown SPC reason codes.

Preserve the original reason code and return a generic translated error.

---

## Translations

User-visible Home Assistant errors should use translated Home Assistant
exceptions rather than hard-coded English strings whenever possible.

When adding an exception, update:

```text
custom_components/spc_flexc/strings.json
custom_components/spc_flexc/translations/en.json
custom_components/spc_flexc/translations/fr.json
```

Translation keys and placeholders must remain consistent.

For example, if `strings.json` contains:

```json
{
  "exceptions": {
    "area_not_ready_zone": {
      "message": "Cannot arm {area}: zone {zone} (ID {zone_id}) is not ready (SPC reason {reason})."
    }
  }
}
```

the corresponding translation must use the same placeholders:

```text
{area}
{zone}
{zone_id}
{reason}
```

Do not add or remove a placeholder in only one language.

Run:

```bash
make check
```

before committing translation changes.

Hassfest and the repository checks should remain green.

---

## Tests

Behaviour changes should include tests whenever practical.

Tests are particularly important for:

- area mode mapping;
- alarm control panel state;
- supported features;
- FlexC reply parsing;
- change-mode prechecks;
- SPC reason decoding;
- global alarm behaviour;
- translations and exception keys;
- event processing;
- coordinator updates.

A bug fix should preferably include a regression test demonstrating the
previous failure.

Run:

```bash
make test
```

or the complete validation suite:

```bash
make check
```

---

## Testing against a real SPC panel

Real-panel testing is extremely valuable for FlexC changes, but must be done
carefully.

Start with read-only commands whenever possible.

Before testing a state-changing command:

- confirm the target area;
- check its current state;
- confirm that another method of controlling the alarm is available;
- understand whether the command can trigger an entry/exit delay or alarm;
- avoid automatic retries;
- verify the resulting state directly from SPC.

Never assume that a command timeout means the command was not executed.

When investigating an unknown FLEXML command, prefer read-only capability or
status requests before attempting state-changing commands.

---

## Diagnostics

Additional SPC diagnostic fields are welcome when they provide useful
information to Home Assistant users.

When adding a diagnostic entity:

- confirm that the field is actually returned by SPC;
- determine its meaning from reliable evidence;
- use an appropriate Home Assistant entity type;
- use the correct device class and unit when applicable;
- mark specialised diagnostics disabled by default when appropriate;
- handle panels where the field is absent;
- do not assume that optional RF, modem or expansion hardware exists.

Diagnostic support should degrade gracefully on panels that do not expose the
field.

---

## Supporting additional SPC hardware

SPC installations vary considerably.

A panel may contain optional:

- RF modules;
- communication modules;
- modems;
- expanders;
- power supplies;
- additional areas;
- different zone configurations.

When adding support for hardware not available to the maintainer, include
sanitised diagnostic information or protocol samples whenever possible.

Do not publish private installation information.

---

## Security and sensitive information

Never include real credentials in:

- source code;
- tests;
- issues;
- pull requests;
- logs;
- screenshots;
- documentation.

This includes:

- FlexC AES-256 encryption keys;
- Command Profile passwords;
- SPC user PINs;
- installer codes;
- IP addresses when they reveal private infrastructure;
- authentication tokens.

Use clearly fake values in examples.

For example:

```text
1111111111111111111111111111111111111111111111111111111111111111
```

for a test AES-256 key.

Before attaching logs to an issue, inspect and redact them.

---

## Reporting bugs

Please use GitHub Issues for bug reports.

Include whenever possible:

- SPC panel model;
- SPC firmware version;
- SPC FlexC integration version;
- Home Assistant version;
- a clear description of the problem;
- steps to reproduce it;
- relevant Home Assistant logs;
- Home Assistant diagnostics.

For alarm-control issues, also include:

- the area involved;
- the requested mode;
- the current mode;
- the SPC reason code if available.

Never include passwords, PINs or encryption keys.

---

## Feature requests

Feature requests are welcome.

For significant protocol or alarm-control changes, please open an Issue before
starting a large implementation.

This helps establish:

- whether the SPC panel exposes the requested feature;
- whether suitable FlexC/FLEXML commands are known;
- how the feature should map to Home Assistant;
- what safety constraints are required.

---

## Pull requests

Before opening a Pull Request:

1. update your branch from `main`;
2. run the formatter;
3. run the complete validation suite;
4. add or update tests;
5. update documentation if user-visible behaviour changed;
6. make sure no credentials or private installation data are present.

Recommended final check:

```bash
make check
git diff --check
git status
```

All CI and Hassfest checks must pass before a Pull Request can be merged.

Keep Pull Requests focused on one logical change whenever possible.

---

## Commit messages

Use short, descriptive commit messages.

Examples:

```text
Add global SPC arm and disarm control
```

```text
Decode SPC zone not-ready reasons
```

```text
Add FlexC ATS diagnostics
```

```text
Improve area change-mode error handling
```

```text
Document SPC FlexC v1.0
```

Avoid generic messages such as:

```text
fix
update
changes
```

---

## Documentation

Update `README.md` when a contribution changes:

- installation;
- SPC configuration;
- Home Assistant configuration;
- available entities;
- alarm behaviour;
- diagnostics;
- limitations.

Update `CHANGELOG.md` for user-visible changes intended for a release.

---

## Code of conduct

Be respectful and constructive when participating in the project.

Technical disagreements are welcome; personal attacks are not.

The goal is to build a reliable and safe Home Assistant integration for SPC
users.

---

## Disclaimer

SPC FlexC is an independent open-source project.

It is not affiliated with, endorsed by, or supported by Siemens, Vanderbilt,
Comelit or Home Assistant.

Contributors are responsible for testing changes carefully before using them
on a live alarm installation.

---

## License

By contributing to SPC FlexC, you agree that your contributions will be
licensed under the same license as the project.

See [LICENSE](LICENSE) for details.