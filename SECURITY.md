# Security Policy

## Supported versions

The latest released version is supported.

Please update to the most recent release before reporting a security issue.

---

## Reporting a vulnerability

If you believe you have found a security vulnerability in **SPC FlexC**, please **do not** open a public GitHub issue.

Instead, report it privately by contacting the maintainer through GitHub or by email if a contact address is available.

Please include:

- a description of the vulnerability;
- affected version(s);
- steps to reproduce;
- potential impact;
- any suggested mitigation.

---

## Sensitive information

Never publish or include the following in bug reports, issues, pull requests, or discussions:

- SPC panel credentials
- FlexC authentication credentials or secrets
- Panel serial numbers or other identifying information when sensitive
- Alarm codes or user credentials
- Network addresses or configuration when sensitive
- Home Assistant secrets
- Home Assistant diagnostics containing authentication or security-sensitive data
- Raw protocol captures containing credentials or sensitive panel information
- Any other private authentication or security information

Please remove or redact sensitive information before sharing logs, diagnostics, or protocol captures.

---

## Scope

This integration communicates with Vanderbilt SPC intrusion alarm systems using the FlexC protocol.

Security reports related to:

- authentication;
- credential storage;
- FlexC communication and encryption;
- panel command authorization;
- alarm arming and disarming controls;
- sensitive data exposure;
- protocol handling;

are especially appreciated.

---

Thank you for helping keep SPC FlexC secure.