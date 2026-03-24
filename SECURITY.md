# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in AgenticAudit, please report it
responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainers directly or use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature on this repository.

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 1 week
- **Fix or mitigation:** Depends on severity, targeting < 30 days for critical issues

## Security Design

AgenticAudit is designed with security in mind:

- **API keys** are stored as SHA-256 hashes, never in plaintext
- **Constant-time comparison** (`hmac.compare_digest`) prevents timing attacks
- **PII detection** helps identify sensitive data before it's stored
- **Field length limits** prevent abuse via oversized payloads
- **No secrets in logs** — only key prefixes are logged on auth failure
- **Global exception handler** prevents stack trace leaks to clients

## Dependencies

We use `uv` for dependency management with a locked `uv.lock` file. Run
`uv sync --frozen` to ensure reproducible builds. We recommend running
`uv audit` periodically to check for known vulnerabilities in dependencies.
