# Security Policy

## Scope

NEXORA Brain is an actively developed portfolio and engineering project. Security reports concerning the current `main` branch are welcome.

## Reporting a vulnerability

**Please do not disclose a suspected vulnerability in a public GitHub issue.** Public reports can expose a weakness before it can be reviewed or fixed.

Use GitHub's private vulnerability reporting / Security Advisory workflow when it is available for this repository. If private reporting is unavailable, contact the repository owner privately through the contact method listed on the owner's GitHub profile and include only the minimum information needed to establish contact.

A useful report should include:

- the affected component or file;
- steps to reproduce the issue;
- expected versus observed behavior;
- potential security impact;
- any safe proof-of-concept details required to reproduce it.

Do not include real credentials, private user data, destructive payloads, or unrelated confidential information.

## Secret handling

Real credentials must never be committed to this repository. Local values belong in `.env`, which is excluded by `.gitignore`; `.env.example` contains non-secret example configuration only.

If a credential is ever exposed, treat it as compromised and revoke/rotate it before considering repository-history cleanup.

## Supported version

Security fixes target the current `main` branch. Historical development snapshots are not separately maintained as supported releases.

## Security boundaries

The repository contains application-level authorization policies and provider-neutral principal claims. These are **not** a replacement for a production identity provider, API gateway, TLS termination, deployment isolation, secret manager, rate limiting, malware scanning, or other infrastructure controls required by a real deployment.

## Responsible disclosure

Please allow reasonable time for investigation and remediation before public disclosure. Do not access data or systems that you do not own or have explicit permission to test.
