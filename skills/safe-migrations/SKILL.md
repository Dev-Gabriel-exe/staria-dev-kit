---
name: safe-migrations
description: Use when changing live schemas, migrating application data, backfilling records, or repairing database inconsistencies.
---

# Migrações seguras

1. Document current and target state, dependencies, lock risks and rollback limits.
2. Back up and rehearse on staging or a disposable database branch.
3. Make changes backward compatible: add, backfill, switch reads/writes, then remove.
4. Batch long backfills with checkpoints and idempotent retries.
5. Verify row counts and business invariants before and after.
6. Require explicit user approval before destructive production mutations.
