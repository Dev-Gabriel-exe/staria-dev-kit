# Security policy / Política de segurança

StarIA Debug Gate is an optional workflow guardrail **not a security boundary**.

Its effective coverage depends on supported, installed and trusted Codex hooks. Unknown tools, shell commands, disabled hooks, and state-file manipulation can bypass or impair its enforcement; no comprehensive sandbox guarantees are provided.

For potentially sensitive reports, do not disclose vulnerabilities, credentials or confidential materials in public Issues. First contact the maintainer privately through GitHub's profile contact options. Avoid attaching secrets even in private reports.

Supported version under active development: `0.1.x`. Security claims must be demonstrated using reproducible tests; limitations should be reported plainly.
