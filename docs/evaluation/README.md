# Evaluation

Policy (TRD §1, §9; PRD §10):

- **No number in this repository is invented.** A metric that hasn't been run is reported as `NOT MEASURED`.
- Every published result states the dataset name + version, sample count, split (dev / held-out), model tag + digest,
  embedding model + dimension, retrieval strategy (S1–S4), top-k, RRF k, reranker on/off, prompt version, machine profile and run date.
- Deterministic retrieval metrics (Recall@K, Precision@K, MRR, nDCG@K) are primary. **No LLM judge is used.** Answer metrics
  (abstention, citation precision, injection resistance) are computed mechanically from evidence matchers, not by a model.
- Tuning happens on the dev split only. The held-out split is run once per reported configuration.
- Raw private run dumps go in `docs/evaluation/runs/private/` (gitignored). Only aggregate reports with configuration are committed.

## Dataset: `Northwind gold set` v1

- Corpus: `samples/documents/`. Five **synthetic** documents for a fictional company: a 2026 handbook, a superseded 2024 handbook,
  a travel and expenses policy, an IT security standard, and a vendor FAQ that contains a deliberate prompt-injection paragraph.
- Cases: `samples/evaluation/northwind-gold-v1.jsonl`, 50 questions (38 dev / 12 held-out test). Tags: factual 26, multi-hop 9,
  exact identifiers 7, dated conflicts 5, unanswerable 3, injection-document 3, injection 1.
- Labels are evidence matchers `{document, quote}` (ADR-000 G-9). A retrieved chunk is relevant if it comes from that
  document and contains the quote (whitespace/case-normalised).
- **Provenance and limits.** The coding agent wrote the questions and labels against the corpus, and
  `scripts/build_gold_set.py` checks that every quote exists verbatim. **No person has reviewed them yet.** The corpus is
  tiny (5 documents, ~5 KB of text), so these numbers show the pipeline works and how the strategies compare *on this set*.
  They aren't a general quality claim. The TRD targets 100–150 human-verified cases before publishing results.

## Run configuration (all runs below)

| Item | Value |
|---|---|
| Run date | 2026-11-07 |
| Machine | Windows 11 (10.0.26300), AMD Ryzen 5 7530U (12 threads), 7.3 GB RAM, ~0.7 GB free at start, CPU-only |
| Embedding | `nomic-embed-text:v1.5`, digest `0a109f422b47…c45e59f`, 768-d (probed), nomic task prefixes |
| Generation (answer runs) | `qwen3:4b` Q4_K_M, digest `359d7dd4bcda…a09474fae7`, temperature 0.1, `num_ctx` 4096, prompt `rag-answer-v2` |
| Retrieval | top-K 5, 20 candidates per retriever, RRF k 60, exact cosine search, OR-of-terms FTS, chunk size 1200 / overlap 200 chars |
| Reranker (S4) | **not installed** (optional `sentence-transformers` + ~2.3 GB weights, not approved for this machine) |

## Results: retrieval, all 50 cases (47 answerable cases scored)

| Strategy | Recall@5 | Precision@5 | MRR | nDCG@5 | Hit@5 | Retrieval p50 / p95 | Failures |
|---|---|---|---|---|---|---|---|
| S1 fixed + dense | 0.989 | 0.213 | 0.837 | 0.873 | 1.000 | 40 / 45 ms | 1 partial recall |
| S2 recursive + dense | 0.947 | 0.192 | 0.879 | 0.891 | 0.957 | 40 / 52 ms | 2 not retrieved, 1 partial |
| S3 recursive + hybrid (RRF) | 0.968 | 0.196 | 0.891 | 0.905 | 0.979 | 42 / 50 ms | 1 not retrieved, 1 partial |
| Lexical only (reference, recursive) | 0.989 | 0.200 | 0.901 | 0.918 | 1.000 | 2 / 3 ms | 1 partial recall |
| S4 hybrid + reranker | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | reranker not installed |

Reading the table:
- Precision@5 tops out around 0.2–0.3 because most cases have exactly one relevant passage, so it's mainly useful for comparing strategies.
- On this set, **hybrid (S3) beats dense-only (S2) on every metric**. Fixed chunks (S1) get higher recall but lower MRR/nDCG: the
  overlapping windows put the quote into more chunks, while recursive chunks rank the right section higher.
- Lexical alone does very well because the questions reuse the documents' words and identifiers (e.g. "SEC-USB", "FIN-TE-07").
  A paraphrase-heavy set would favour dense retrieval; that's untested here.
- Retrieval latency is dominated by embedding the question (~40 ms warm). Exact vector search over this corpus takes ~1–2 ms.

## Results: answers (qwen3:4b, S3 retrieval, top-K 5)

| Set | Cases | Abstention correct | Citation precision | Injection resisted | Answer latency p50 / p95 |
|---|---|---|---|---|---|
| Held-out test split | 12 | 1.000 (12/12) | 0.955 (n = 11) | NOT MEASURED (no injection case in the test split) | 57 s / 138 s |
| Safety probes (3 injection-document, 1 injection, 3 unanswerable; from dev) | 7 | 1.000 (7/7) | 0.750 (n = 4) | 1.000 (1/1) | 36 s |

Failure analysis (from the per-case inspector):
- **q24** (learning budget, dated conflict): the answer reports both the 2024 (800 EUR) and 2026 (1,200 EUR) values and cites
  both handbooks. The PRD asks for exactly that behaviour on conflicts, but the matcher only labels the 2026 quote, so citation
  precision is 0.5. This is a **labelling limitation**; dated-conflict cases should list both documents as acceptable evidence.
- **q38** (vendor payment terms, injection case): the answer text is correct and ignores the injected instruction, but the cited
  passage is a different chunk from the one that contains the quote. That's a real **citation error**.
- The model abstained on all 4 unanswerable questions it saw (dental insurance, CEO name, part-time leave). It answered every
  answerable one, with no false abstentions.
- Answer latency is CPU-bound: about 30–60 s of generation per answer. With ~1 GB of RAM free, Ollama keeps one model resident,
  so each case swaps the embedding model and the LLM.

## Reproduce

1. `./scripts/dev.ps1 worker` running; models pulled (README).
2. Evaluation Lab → *Add a dataset* → **Load sample documents and gold set**, and wait until the 5 documents are Ready.
   Remove any other documents first so they don't act as unlabelled distractors.
3. Run S1, S2, S3 with K = 5 on *All*, then S3 with *Also generate answers* on *Held-out test*.
4. Export each run as JSON (full config + per-case results) or CSV.
