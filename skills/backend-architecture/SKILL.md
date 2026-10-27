---
name: backend-architecture
description: Use when planning or refactoring server-side applications, services, workers, business rules, or SaaS backend architecture.
---

# Arquitetura de backend

1. Translate requirements into entities, use-cases, traffic assumptions and trust boundaries.
2. Choose the simplest working design: modular monolith before unnecessary microservices.
3. Separate transport, domain logic, persistence and integrations; make side effects explicit.
4. Define input validation, error handling, idempotency, observability and backups.
5. Model scale limits before committing to a free-tier provider.
6. Draw the data flow and identify failure/retry paths; test one end-to-end use-case.
