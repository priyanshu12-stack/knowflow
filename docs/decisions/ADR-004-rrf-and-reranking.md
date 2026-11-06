# ADR-004: Hybrid retrieval with RRF; reranker optional and off

- Status: Accepted (M5) on the evidence in docs/evaluation/README.md. Revisit with a larger, human-verified set.
- Milestone: M5

## Context

TRD §9 defines S1–S4 and asks whether reranking improves ranking enough to justify its latency.
The reference machine is CPU-only with 7.3 GB of RAM, already shared by `qwen3:4b` and the
embedding model.

## Decision

- **Fusion**: Reciprocal Rank Fusion, `score = Σ 1/(k + rank)` with k = 60, over the top 20
  dense and top 20 lexical candidates. It's rank-based, so cosine similarity and `ts_rank_cd` never need a common scale.
  Per-retriever ranks are stored with every answer and evaluation result.
- **Default for Ask KnowFlow stays `dense`** in the UI for now. The measured S3 (hybrid) advantage over S2 on the
  sample set is small (MRR 0.891 vs 0.879, nDCG 0.905 vs 0.891) but consistent. Users can pick hybrid per question,
  and the default switches once the human-verified set confirms it.
- **Reranker**: a `CrossEncoder` adapter for `BAAI/bge-reranker-v2-m3` exists behind
  `ENABLE_RERANKER` / the per-request `rerank` flag. It's loaded lazily once per process and is optional
  (`pip install -e "apps/api[reranker]"`). It is **not installed** on the reference machine. The ~2.3 GB weights plus torch don't fit
  next to the LLM in the available RAM, and the download wasn't approved. S4 is therefore NOT MEASURED. The UI
  disables it with that reason, and the API refuses it with the install command.
- The similarity abstention threshold (0.45 cosine) applies only to dense mode. RRF and reranker scores
  aren't on a cosine scale, so in those modes the model's own abstention and citation verification decide.

## Consequences

- Hybrid adds about 2 ms per question (FTS + fusion) on the sample corpus.
- S4 needs a machine with roughly 4 GB more free RAM, or a smaller reranker. Either has to be measured on the same dataset version.
