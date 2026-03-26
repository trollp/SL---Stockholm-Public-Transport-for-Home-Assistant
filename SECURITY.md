# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public issue**.

Instead, report it via GitHub's private vulnerability reporting:
👉 [Report a vulnerability](../../security/advisories/new)

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect a response within 5 business days.

## Scope

This integration:
- Makes **outbound read-only HTTP requests** to the public SL Transport API (`transport.integration.sl.se`)
- Requires **no API keys or credentials**
- Stores only stop configuration data (site IDs, route preferences) in Home Assistant config entries
- Does not collect, transmit, or store any personal data beyond what Home Assistant itself handles

## Out of Scope

- The Home Assistant instance itself
- Network-level attacks against the SL API
