# Contributing to SPC FlexC

Thank you for your interest in contributing to SPC FlexC.

SPC FlexC is a custom Home Assistant integration for Siemens / Vanderbilt /
Comelit SPC alarm panels using the native FlexC protocol. Contributions are
welcome, including bug fixes, additional hardware support, FlexC diagnostics,
event decoding, FLEXML commands, translations, documentation and tests.

Because the integration communicates with a security system and can perform
state-changing operations, protocol and control changes require particular
care.

---

## Development setup

Clone the repository and install the development dependencies:

```bash
git clone https://github.com/minimicro34/ha-spc-flexc.git
cd ha-spc-flexc
```

The project currently targets Python 3.14 for its development commands.

The Makefile provides the standard workflow:

```bash
make compile
make format
make format-check
make lint
make typecheck
make test
make coverage
make check
make clean
```

### Formatting, validation and coverage

These commands have different purposes and should not be confused:

- `make format` applies Ruff formatting and may modify Python files;
- `make check` runs compilation, formatting verification, linting, type
  checking and the standard test suite;
- `make coverage` runs the test suite with coverage measurement and enforces
  the repository minimum coverage threshold of 80%.

`make check` does **not** run `make coverage`.

Before submitting a Pull Request or preparing a release, run both:

```bash
make check
make coverage
```

It is also recommended to verify the working tree:

```bash
git diff --check
git status
```

All checks, coverage validation, CI and Hassfest must pass.

Coverage data such as `.coverage` and generated HTML coverage reports are
local development artifacts and must not be committed.

---

## Code quality

Contributions should follow the conventions already used by the integration
and Home Assistant. In particular:

- keep asynchronous operations non-blocking;
- use Home Assistant entity and coordinator patterns;
- keep typing annotations accurate;
- keep Ruff formatting and linting clean;
- avoid broad exception handlers unless they are deliberately required at a
  task boundary;
- add or update tests when changing behaviour;
- preserve compatibility with the supported Home Assistant version.

Do not disable linting, typing or coverage rules merely to make validation
pass. Fix the underlying issue whenever possible.

---

## Protocol evidence and hardware validation

SPC installations vary by panel model, firmware and installed modules.
Undocumented protocol fields must not be assigned a meaning solely from a
name, a single example or an assumption.

When adding or changing protocol mappings:

1. prefer read-only discovery and status commands first;
2. retain useful raw diagnostic data when semantics are still uncertain;
3. validate behaviour against real SPC hardware or reliable protocol evidence;
4. add regression tests for the validated mapping;
5. document hardware-dependent limitations where appropriate.

When hardware is not available to the maintainer, sanitised diagnostics or
protocol captures are especially useful.

---

## FlexC command safety

SPC FlexC controls a real alarm system. Any contribution involving commands
that change panel state must preserve the safety rules below.

### Never automatically retry state-changing commands

Commands such as Full Set, Unset, Part Set, zone control and Mapping Gate
control must **never be automatically retried** after an uncertain timeout or
connection failure.

A timeout does not prove that the SPC panel did not execute the command.
Automatically resending it could therefore cause an unexpected second
operation.

Read-only requests may use bounded connection recovery or retry mechanisms
where appropriate.

### Precheck before arming

Area arming operations must use the SPC change-mode capability precheck before
sending the state-changing command. If the panel reports that the area is not
ready, the state-changing command must not be sent.

### Global arming

Global Full Set is implemented as coordinated individual area commands. Before
the first Full Set command is sent, every relevant area must be prechecked. If
any precheck fails, the global operation must stop before changing an area.

This reduces the risk of partial arming but cannot make the operation atomic:
communication or panel state can still change after the prechecks.

### Verify resulting state

Whenever practical, refresh and verify SPC state after a command instead of
assuming that an accepted command means the requested final state has already
been reached.

---

## Validated SPC controls

The currently validated area mode mapping is:

| SPC mode | Meaning | Home Assistant |
|---:|---|---|
| `0` | Unset | Disarmed |
| `1` | Part Set A | Armed Home |
| `2` | Part Set B | Armed Night |
| `3` | Full Set | Armed Away |

Validated zone control actions are:

| ACTION | Meaning |
|---:|---|
| `0` | Inhibit |
| `1` | De-inhibit |
| `2` | Isolate |
| `3` | De-isolate |

Zone isolation and inhibition commands must only be exposed when the
corresponding SPC capability field explicitly allows the requested operation.

Mapping Gate control uses the SPC-reported Mapping Gate state and verifies the
result after a state-changing request.

Do not extend these mappings to other SPC objects without evidence that the
same semantics apply.

---

## SPC change-mode errors

Validated reason codes in the form `1000 + zone_id` identify the zone
preventing an arming operation. The integration should resolve that zone
against coordinator data and include both its name and ID when possible.

Validated reason `10006` is handled separately as Engineer / Installer mode.
Validated reason `2007` represents an active system fault; known active faults
may be included in the Home Assistant error when available.

Do not invent meanings for unknown reason codes. Preserve the original code and
return a generic translated error.

---

## Translations

When adding or changing user-visible strings, keep these files consistent:

```text
custom_components/spc_flexc/strings.json
custom_components/spc_flexc/translations/en.json
custom_components/spc_flexc/translations/fr.json
```

Translation keys and placeholders must match across files and languages.

---

## Tests

Behaviour changes should include tests whenever practical. Regression tests are
particularly important for protocol parsing, coordinator updates, entity
creation, alarm control, zone control, Mapping Gates, X-BUS discovery, event
processing and error handling.

For a quick test run:

```bash
make test
```

For final validation, use both commands:

```bash
make check
make coverage
```

The CI coverage threshold is a minimum, not a target to satisfy with artificial
tests. Prefer tests that exercise meaningful behaviour and failure paths.

---

## Testing against a real SPC panel

Real-panel testing is extremely valuable for FlexC changes, but must be done
carefully. Start with read-only commands whenever possible.

Before testing a state-changing command:

- confirm the target object and its current state;
- confirm that another method of controlling the alarm is available;
- understand whether the command can trigger an alarm or other physical action;
- avoid automatic retries;
- verify the resulting state directly from SPC.

Never assume that a command timeout means the command was not executed.

---

## Diagnostics and additional hardware

Additional diagnostic fields are welcome when they provide useful information.
Confirm that a field is actually returned by SPC and that its meaning is
supported by evidence before exposing it as a normal Home Assistant entity.

Use diagnostic entities or raw diagnostics for specialised or uncertain data,
handle absent optional fields gracefully, and do not assume that RF, modem,
X-BUS or expansion hardware exists on every installation.

---

## Security and sensitive information

Never include real credentials or private installation data in source code,
tests, Issues, Pull Requests, logs, screenshots or documentation.

This includes FlexC AES-256 keys, Command Profile passwords, SPC user PINs,
installer codes, authentication tokens and private infrastructure details.
Inspect and redact diagnostics and captures before publishing them.

---

## Reporting bugs and feature requests

Please use GitHub Issues. For bug reports, include whenever possible:

- SPC panel model and firmware version;
- SPC FlexC integration version;
- Home Assistant version;
- steps to reproduce the problem;
- relevant sanitised logs and diagnostics.

For significant protocol or state-changing features, opening an Issue before a
large implementation is recommended so that protocol evidence, Home Assistant
mapping and safety constraints can be established first.

---

## Pull requests

Before opening a Pull Request:

1. update your branch from `main`;
2. run `make format` if needed;
3. add or update meaningful tests;
4. update documentation for user-visible behaviour;
5. run `make check`;
6. run `make coverage`;
7. run `git diff --check`;
8. make sure no credentials, captures or generated coverage data are present.

Keep Pull Requests focused on one logical change whenever possible.

Use short, descriptive commit messages such as:

```text
Add Mapping Gate control
Test FlexC connection lifecycle
Document SPC FlexC v1.1.0
```

---

## Documentation

Update `README.md` when a contribution changes installation, configuration,
available entities, alarm behaviour, controls, diagnostics or known
limitations. Update `CHANGELOG.md` for user-visible changes intended for a
release.

---

## Code of conduct

Be respectful and constructive when participating in the project. Technical
disagreements are welcome; personal attacks are not.

---

## Disclaimer

SPC FlexC is an independent open-source project. It is not affiliated with,
endorsed by, or supported by Siemens, Vanderbilt, Comelit or Home Assistant.
Contributors are responsible for testing changes carefully before using them on
a live alarm installation.

---

## License

By contributing to SPC FlexC, you agree that your contributions will be
licensed under the same license as the project. See [LICENSE](LICENSE) for
details.
