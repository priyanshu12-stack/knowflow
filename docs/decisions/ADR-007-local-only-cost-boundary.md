# ADR-007: Local-only cost boundary

- Status: Accepted (2026-11-06)

## Context

TRD §1 and §13 require zero paid inference APIs and forbid claiming that free model weights mean zero cost.

## Decision

| Free in the sense of "no payment, no API key" | Still costs the user something |
|---|---|
| Ollama runtime, Qwen3 weights (Apache-2.0 per the Ollama listing; re-verify at M4), nomic-embed-text, bge-reranker-v2-m3 (Apache-2.0 model card) | CPU/GPU time, RAM, disk (~3 GB of models + data), electricity |
| PostgreSQL, pgvector, FastAPI, Next.js, all other OSS dependencies | Initial download bandwidth for dependencies and models |
| GitHub Actions within included free quota | Any public hosting: not promised. Free tiers have limits and may require payment details |

Rules:

- No code path calls a paid or hosted inference API. There are no provider adapters other than Ollama and the local Sentence-Transformers reranker.
- `.env.example` contains no provider API-key variables.
- A CI check (`scripts/check_no_paid_apis.py`, added when the models module lands at M3) fails if known paid-provider SDKs appear in dependencies.
- If a model is unavailable, the app reports the missing prerequisite. It never falls back to a cloud API.
- The Ollama port is never exposed publicly. A public demo would use recorded video or a frontend-only deploy (TRD §13).
