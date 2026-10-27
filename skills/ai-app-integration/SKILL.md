---
name: ai-app-integration
description: Use when adding LLM features, RAG, vector search, autonomous actions, chat agents, or structured extraction to applications.
---

# Integrações de IA e agentes

1. Specify concrete user task, evaluation dataset, accuracy/cost/latency budget and failure response.
2. Prefer narrow deterministic automation over LLM calls when possible.
3. Use retrieval citations and abstention for document Q&A; never invent source evidence.
4. Validate structured outputs, constrain tool privileges and prevent prompt-injection side effects.
5. Evaluate groundedness, error rates, latency and abuse before release.
6. Follow R$0 cost policy: avoid required paid model APIs or GPU hosting without explicit approval.
