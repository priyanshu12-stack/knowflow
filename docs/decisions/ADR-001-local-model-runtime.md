# ADR-001: Local-first model runtime

- Status: Proposed (2026-11-06). Becomes Accepted when the model digest and a smoke benchmark are recorded at M3/M4.
- Milestone: M0 (choice), M3/M4 (verification)

## Context

- TRD §4 requires local inference through Ollama, Qwen3 for generation, and provider-agnostic interfaces.
- The dev machine has 7.3 GB RAM, about 0.8 GB of it free at audit time, a CPU-only Ryzen 5 7530U, and no usable GPU.
- Ollama 0.17.1 is installed and running. No models were pulled at audit time.

## Decision

- Runtime: **Ollama** (native Windows install), at `http://localhost:11434`.
- Generation default: **`qwen3:4b`**. This is the TRD "Low-resource" profile, which matches an 8 GB-class machine.
  `qwen3:8b` stays the documented recommendation for 16 GB+ machines and is selectable through config.
- Embedding default: **`nomic-embed-text:v1.5`** (pinned tag, not `latest`).
- Reranker: **disabled** (`ENABLE_RERANKER=false`). It gets enabled only after M5 measures quality and latency.
- Model tags are pinned in `.env.example`. The model digest (`ollama show`/`/api/tags`) is recorded in every evaluation run.
- The app never pulls models at runtime. When a model is missing, it shows the exact `ollama pull` command.

## Verified at M3 (2026-11-07, from the local Ollama 0.17.1 runtime)

| Item | Value |
|---|---|
| `qwen3:4b` | id `359d7dd4bcda`, 2.50 GB on disk, Q4_K_M, 4.0B params, capabilities `completion, tools, thinking`, model context 262,144 tokens (KnowFlow uses `num_ctx` 4096 to bound RAM), license Apache-2.0 (from `ollama show`) |
| `nomic-embed-text:v1.5` | digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`, 274 MB, F16, 137M params, context 2048; **probed dimension 768** (stored in `embedding_versions`) |
| Structured output | `qwen3:4b` with a JSON Schema `format` and `think: false` returns schema-valid JSON (live test `tests/integration/test_real_ollama.py`) |
| Small-machine behaviour | One HTTP 500 was observed while loading `qwen3:4b` with the embedding model resident and ~0.9 GB RAM free. It wasn't reproducible; the client now retries a 5xx once and surfaces Ollama's own error text |
| Peak RAM, tokens/sec, cold-load time | NOT MEASURED yet (recorded with the M5 evaluation runs) |

`think: false` is sent on every chat call: qwen3 is a hybrid reasoning model and the thinking
trace would cost several seconds of CPU per answer without being shown to the user.

## Consequences

- Answer quality on complex synthesis and SQL clarification may be weaker than with 8B. TRD §4.1 notes this. It gets measured on the gold set, not assumed.
- `qwen3:4b` and the reranker likely can't stay resident together in 7.3 GB. S4 runs may need sequential model loading, and the timing data will reflect that.
