---
name: database-modeling
description: Use when planning relational schemas, Postgres or Neon tables, indexes, constraints, joins, or SQL query performance.
---

# Modelagem e consultas SQL

1. Define real entities, relationships, cardinality, lifecycle and uniqueness before writing tables.
2. Use proper keys, foreign keys, constraints, transactions and suitable types.
3. Avoid storing interchangeable business entities as undifferentiated JSON.
4. Use EXPLAIN/ANALYZE for actual slow queries, and indexes based on workload.
5. Consider tenant isolation, retention, backup and schema evolution.
6. Supply migration SQL and reversible test fixtures; never operate on production data without explicit approval.
