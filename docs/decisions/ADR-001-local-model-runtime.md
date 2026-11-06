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

## To verify at M3/M4 (not yet measured)

| Item | Value |
|---|---|
| `qwen3:4b` digest, quantization, disk size, context window, license | NOT MEASURED |
| `nomic-embed-text:v1.5` digest and returned vector dimension | NOT MEASURED (probed at startup, never assumed) |
| Peak RAM during generation, tokens/sec, cold-load time | NOT MEASURED |

## Consequences

- Answer quality on complex synthesis and SQL clarification may be weaker than with 8B. TRD §4.1 notes this. It gets measured on the gold set, not assumed.
- `qwen3:4b` and the reranker likely can't stay resident together in 7.3 GB. S4 runs may need sequential model loading, and the timing data will reflect that.
