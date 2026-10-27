---
name: api-design
description: Use when creating, debugging, documenting, or versioning HTTP APIs, REST endpoints, webhooks, or typed contracts.
---

# APIs e contratos

1. Define route, method, auth, schema, permissions, success and error responses.
2. Validate data on the server regardless of frontend validation.
3. Keep stable response envelopes and meaningful status codes; avoid leaking internals.
4. For webhooks verify signatures, deduplicate event IDs, constrain replay window and retry safely.
5. Document pagination, rate limits and sample requests without real secrets.
6. Include contract tests for invalid, unauthorized and idempotent calls.
