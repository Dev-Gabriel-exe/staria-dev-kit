---
name: zero-cost-deploy
description: Use when deploying a project under a strict no-charge budget, selecting free hosting, limiting cloud resources, or avoiding surprise fees.
---

# Deploy com orçamento zero

1. Treat R$0 hosting/API cost as a hard constraint until the project has at least two paying clients.
2. Prefer existing GitHub, Vercel and Neon connections if their free limits cover the use-case; do not duplicate services.
3. Verify *current* free quotas, commercial-use terms, credits, billing behavior and card requirement before recommending provisioning.
4. Never enable paid upgrades, auto-scaling with billing or paid trials without explicit approval.
5. Provide a budget gate: predicted usage, limit trigger, safe fallback and what breaks when quota runs out.
6. Confirm production build, environment variables, health checks and rollback plan.
