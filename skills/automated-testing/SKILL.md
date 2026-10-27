---
name: automated-testing
description: Use when adding features or fixing bugs requiring unit, integration, contract, or end-to-end tests.
---

# Testes automatizados

1. Convert the desired behavior to observable assertions including failures and boundaries.
2. Run a targeted test showing the original failure or unmet behavior where possible.
3. Implement the smallest change, keep fixtures deterministic and isolate side effects.
4. Run related tests, then full build/typecheck/lint when available.
5. Cover auth, permissions, tenant boundaries and regression paths for critical flows.
6. Report commands executed, pass/fail results and what was not run honestly.
