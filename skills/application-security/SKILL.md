---
name: application-security
description: Use when reviewing app security, input validation, secret management, APIs, uploads, dependency risks, or security-sensitive changes.
---

# Segurança de aplicações

1. Identify assets, actors, attack surface and privileges for the feature.
2. Validate/authorize server-side; use parameterized queries and output encoding.
3. Enforce least privilege, secure transport, file type/size validation and rate limits.
4. Check SSRF, XSS, injection, CSRF and cross-tenant access for relevant flows.
5. Never include secret material in logs, messages, commits or plugin files.
6. Supply prioritized remediations and validation tests; no unverified security guarantees.
