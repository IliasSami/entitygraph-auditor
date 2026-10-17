# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within EntityGraph Auditor:
1. Do not open a public issue.
2. Email security findings or remediation patches to the maintainers or report via private security advisory.
3. Include a reproducible proof of concept, affected component, and proposed fix.

## Core Security Controls

1. **Untrusted Content Demarcation**: All user-supplied content and fetched web pages are treated as untrusted input. They are isolated in explicit boundary markers (`<untrusted_content>`) to mitigate indirect prompt injection.
2. **SSRF Prevention**: URL fetching restricts outbound connections:
   - Private IP ranges (RFC 1918, RFC 4193, loopback `127.0.0.0/8`, `::1`) are strictly rejected.
   - Cloud metadata endpoints (e.g. `169.254.169.254`) are blocked.
   - Max response payload sizes are enforced to prevent resource exhaustion.
3. **Secret Hygiene**: Provider API keys are never written to audit traces, logs, or reports.
4. **Local Isolation**: By default, EntityGraph Auditor binds to `127.0.0.1` and runs in single-tenant local mode with no external tracking or telemetry.
