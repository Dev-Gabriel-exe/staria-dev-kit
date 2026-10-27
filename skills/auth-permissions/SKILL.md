---
name: auth-permissions
description: Use when implementing login, sessions, OAuth, role-based access, multitenancy, password reset, or authorization.
---

# Autenticação e autorização

1. Distinguish authentication (identity) from authorization (permission on each resource).
2. Prefer mature libraries and managed primitives if within the cost budget.
3. Check ownership on server for every tenant-scoped record; deny by default.
4. Secure cookies and tokens, CSRF strategy, redirects, session expiration and recovery.
5. Store secrets outside source control and redact logs.
6. Test privilege escalation, broken object-level authorization and logout.
