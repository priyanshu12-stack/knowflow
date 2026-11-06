# Evaluation

Policy (TRD §1, §9; PRD §10):

- **No number in this repository is invented.** A metric that hasn't been run is reported as `NOT MEASURED`.
- Every published result states the dataset name + version, sample count, split (dev / held-out), model tag + digest,
  embedding model + dimension, retrieval strategy (S1–S4), top-k, RRF k, reranker on/off, prompt version, machine profile and run date.
- Deterministic retrieval metrics (Recall@K, Precision@K, MRR, nDCG@K) are primary. LLM-judge metrics
  (faithfulness, answer correctness, citation precision) are labelled **model-judged estimates**, and a sample gets manually audited.
- Tuning happens on the dev split only. The held-out split is run once per reported configuration.
- Raw private run dumps go in `docs/evaluation/runs/private/` (gitignored). Only aggregate reports with configuration are committed.

## Results

| Strategy | Recall@K | Precision@K | MRR | nDCG@K | Abstention acc. | p50 / p95 latency |
|---|---|---|---|---|---|---|
| S1 fixed + dense | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| S2 recursive + dense | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| S3 hybrid + RRF | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| S4 hybrid + RRF + rerank | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
