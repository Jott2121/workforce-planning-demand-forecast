# Security Policy

## Supported versions

This project is actively maintained. Security fixes target the latest version on
the `main` branch.

| Version          | Supported |
| ---------------- | --------- |
| latest (`main`)  | yes       |
| older tags       | no        |

## Reporting a vulnerability

Please do not open a public issue for security vulnerabilities.

Report privately through GitHub's
[Report a vulnerability](https://github.com/Jott2121/workforce-planning-demand-forecast/security/advisories/new)
flow (the repository's Security and Advisories tab). I aim to acknowledge reports
within 72 hours and to ship a fix or mitigation for confirmed issues as quickly
as is practical.

When reporting, please include a description of the issue and its impact, steps
to reproduce (a minimal proof of concept if possible), and any suggested
remediation.

## Scope

This is workforce capacity modeling and demand forecasting: a Streamlit UI over a tested `src/` core. Findings of
interest include unsafe deserialization or file handling in data loading,
injection via user-supplied inputs in the app, and supply-chain risks in CI.
This repository pins its GitHub Actions to commit SHAs and runs CodeQL and
Dependabot to reduce that surface.

Thanks for helping keep it solid.
