# KnowFlow — Quick Revision (one sitting)

> The night-before sheet. Facts verified against commit `65af69c`. Details:
> [Master guide](KNOWFLOW_ENGINEERING_AND_INTERVIEW_MASTER_GUIDE.md) ·
> [Question bank](KNOWFLOW_INTERVIEW_QUESTION_BANK.md) · [Presentation](KNOWFLOW_INTERVIEW_PRESENTATION.md)

## 1. Summary in 8 lines

- **What:** local-first knowledge workspace — cited RAG answers, safe Text-to-SQL with clarification,
  an evaluation lab.
- **Stack:** Next.js 16 / React 19 / TS → FastAPI (Python 3.12) + worker → PostgreSQL 16 + pgvector +
  FTS → Ollama (`qwen3:4b`, `nomic-embed-text:v1.5` 768-d).
- **Core claims:** citations verified against supplied passages; abstain when unsupported; SQL is AST-
  validated and executed read-only; retrieval measured with deterministic metrics.
- **Built:** 6–8 Nov 2026, solo, with an AI coding agent (58/60 commits co-authored); tag `v1.0.0-rc.1`.
- **Deployed:** Azure for Students VM, on demand, HTTPS + password. HF Spaces needs PRO (not deployed).
- **Tests:** 282 pytest (+3 opt-in), 80 Vitest, 28 Playwright; mypy strict; CI configured, never run on GitHub.
- **Best result:** S3 hybrid MRR 0.891 / nDCG 0.905 vs S2 dense 0.879 / 0.891 (50 synthetic cases).
- **Known failure:** dated conflict — model cited the superseded 2024 handbook (24 vs 26 days).

## 2. Architecture on one page

```
Browser ──same-origin /api/v1──► Next.js (rewrites, 600 s proxy timeout)
                                   │
                                   ▼
                     FastAPI :8000 (sync def endpoints, threadpool)
   middleware: request id + JSON log │ upload size limit (411/413)
   routers (10, 45 ops) → services → SQLAlchemy 2 / psycopg 3
        │                │                      │
        │                ▼                      ▼
        │        Ollama :11434          PostgreSQL 16 + pgvector
        │   /api/embed  /api/chat       knowflow (22 tables): documents, jobs,
        │   qwen3:4b    nomic 768-d     sections, chunks(+tsvector GIN),
        │                               chunk_embeddings(vector), messages, eval…
        ▼                               knowflow_demo (sales) ← knowflow_reader (SELECT only)
Worker process: claim job FOR UPDATE SKIP LOCKED → extract (child process, 120 s)
  → chunk fixed+recursive → embed (batch 16) → ONE transaction → ready
  (idle → evaluation runs)
```

## 3. Technologies and why (one line each)

| Tech | Why |
|---|---|
| FastAPI + Pydantic | Typed validation + OpenAPI; model JSON validated like a request |
| Sync endpoints | psycopg async unsupported on Windows Proactor loop; nothing to gain single-user |
| PostgreSQL + pgvector + FTS | One transactional store for data, vectors and keywords (ADR-003) |
| Exact vector search | Fast at this size; TRD "HNSW only if measured"; untyped `vector` column |
| Postgres job queue | One datastore; `SKIP LOCKED`; job state transactional with documents |
| Ollama | Free, local, digests, JSON-schema `format` (ADR-001/007) |
| qwen3:4b (Q4_K_M) | Fits a 7.3 GB CPU laptop; `think: false` |
| nomic-embed-text:v1.5 | Small, strong, 768-d, task prefixes (ADR-002) |
| SQLGlot | AST validation (regex can't see DELETE inside a CTE) |
| Fernet | Encrypt stored SQL passwords; write-only API |
| Next.js rewrites | No CORS, API port stays private |
| Caddy (Azure) | Auto HTTPS + basic auth; only public listener |

**Not used:** LangChain, LlamaIndex, LangGraph, agents/tools, a vector DB, HNSW, Redis/Celery,
RAGAS/LLM judge, hosted APIs, Kubernetes, exact tokenizer.

## 4. Critical numbers and defaults

| Setting | Value |
|---|---|
| Chunk size / overlap | 1200 / 200 chars (overlap only in `fixed`) |
| Token estimate | `ceil(chars / 4)` |
| Candidates per retriever / chat top_k / eval K | 20 / 6 / 5 |
| RRF k | 60 |
| Weak-evidence gate | dense max cosine < 0.45 → abstain (dense mode only) |
| Context budget | 6000 chars |
| RAG temperature / num_ctx / num_predict | 0.1 / 4096 / 700 (SQL: 0.0, 1000) |
| Generation timeout / concurrent generations / queue wait | 300 s / 1 / 10 s → 429 |
| Upload limit / PDF pages / extraction timeout / max chars | 25 MB / 500 / 120 s / 2,000,000 |
| Job attempts / backoff / stale after | 3 / 30 s × 2^(n−1) / 300 s |
| SQL statement / lock timeout / rows | 5 s / 1 s / 500 (fetch 501) |

## 5. Formulas

- **Cosine similarity:** `cos(a,b) = a·b / (‖a‖‖b‖)`; pgvector `<=>` = `1 − cos`; KnowFlow score = `1 − distance`.
- **RRF:** `score(d) = Σ_r 1/(k + rank_r(d))`, k = 60. Example: dense 1 + lexical 3 = 1/61 + 1/63 = **0.0323**.
- **Recall@K** = evidence items found in top K / evidence items.
- **Precision@K** = relevant in top K / K (≈ 0.2 ceiling here: one relevant passage per case).
- **MRR** = mean(1 / rank of first relevant).
- **nDCG@K** = DCG/IDCG, `DCG = Σ gain_i / log2(i+1)`; ranks 1 & 3 of 2 items → 1.5 / 1.631 = **0.920**.
- **Abstention correct** = `abstained == unanswerable`. **Citation precision** = relevant cited / cited.
- **Injection resisted** = answer doesn't contain "PWNED".

## 6. Results (exact; 2026-11-07, laptop, CPU)

| Strategy | Recall@5 | P@5 | MRR | nDCG@5 | Hit@5 | p50/p95 |
|---|---|---|---|---|---|---|
| S1 fixed+dense | 0.989 | 0.213 | 0.837 | 0.873 | 1.000 | 40/45 ms |
| S2 recursive+dense | 0.947 | 0.192 | 0.879 | 0.891 | 0.957 | 40/52 ms |
| S3 hybrid (RRF) | 0.968 | 0.196 | 0.891 | 0.905 | 0.979 | 42/50 ms |
| Lexical only | 0.989 | 0.200 | 0.901 | 0.918 | 1.000 | 2/3 ms |
| S4 + reranker | NOT MEASURED | | | | | |

Answers (S3): held-out 12 → abstention 12/12, citation precision 0.955 (n=11), p50/p95 57/138 s.
Safety probes 7 → abstention 7/7, citation precision 0.750 (n=4), injection 1/1.

## 7. API flows (memorise four)

1. **Upload:** `POST /documents` → 202 (409 duplicate → `?on_duplicate=skip|reindex|new_version`) → poll `GET /documents` (2 s).
2. **Ask:** `POST /chat/query {question, retrieval_config:{mode}}` → `AnswerOut` → `PUT /messages/{id}/feedback`.
3. **SQL:** `POST /sql/query` → `clarification_required` (glossary, no model) → `POST /sql/query` + `clarification_context` → `executed`.
4. **Eval:** `POST /evaluations/sample` → `POST /evaluations/runs {preset:"S3"}` → 202 → poll `GET /evaluations/runs/{id}` → `GET …/export?format=csv`.

45 operations total; error envelope `{"error":{code,message,request_id,…}}`; no auth in the app.

## 8. 50 highest-priority questions (one-line answers)

1. *Explain KnowFlow in 30 s.* → Local RAG with verified citations + safe Text-to-SQL that clarifies + evaluation lab; Ollama + Postgres/pgvector.
2. *Request lifecycle for a question?* → UI → Next proxy → `chat_query` → `ask` → `retrieve` → gate → `answer_question` → `verify_citations` → persist → `AnswerOut`.
3. *How do you prevent hallucinated citations?* → Drop `[n]` not in 1..n_sources; no valid citation → abstain `unsupported`.
4. *Does that prove faithfulness?* → No; provenance only. Faithfulness NOT MEASURED.
5. *Four abstention reasons?* → no_sources, weak_evidence, model_abstained, unsupported.
6. *Why hybrid?* → Dense = paraphrase, lexical = identifiers; S3 > S2 on every metric.
7. *Why RRF?* → Rank-based; no score normalisation; k = 60.
8. *Compute RRF for ranks 1 and 3.* → 0.0323.
9. *Why did FTS return 0 hits?* → `plainto_tsquery` ANDs terms; KnowFlow ORs lexemes, ranks with `ts_rank_cd`.
10. *Fixed vs recursive results?* → Fixed: higher recall (0.989) but lower MRR (0.837); recursive ranks better.
11. *Does recursive use overlap?* → No; only fixed (200 chars).
12. *Why pgvector, not a vector DB?* → One transaction for chunks+vectors+ready; small scale; ADR-003.
13. *Is there an HNSW index?* → No; exact search; untyped `vector` column.
14. *What gets embedded?* → section path + "\n" + chunk text, with `search_document:` prefix.
15. *Why probe the dimension?* → Never assume; mismatch → `embedding_dimension_changed`.
16. *Embedding model changes?* → New `embedding_versions` row; search filters by active version; re-index.
17. *Weak-evidence threshold?* → 0.45 cosine, dense mode only.
18. *Context budget?* → 6000 chars, de-duplicated, rank order.
19. *How is the model's JSON validated?* → `format` schema + `parse_json_object` + Pydantic `ModelAnswer`.
20. *Invalid JSON?* → `model_invalid_output` 503; truncated → `model_output_truncated`.
21. *Temperature/top-p?* → 0.1 RAG, 0.0 SQL; top-p not configured.
22. *Why `think: false`?* → Qwen3 reasoning trace not needed; saves CPU.
23. *Prompt-injection defence?* → Untrusted `<source>` blocks, rule 4, escaping, JSON only, no tools, citation check.
24. *Injection evidence?* → Real-model test + injection metric 1/1; live vendor-FAQ check refused.
25. *SQL flow?* → glossary → role check → introspect → model → SQLGlot → read-only execute.
26. *Why clarify "best"?* → Revenue vs orders vs AOV are different queries/answers.
27. *Clarification without a model call?* → Glossary `ambiguous` term matched by word-boundary regex.
28. *Validator rules?* → one statement, SELECT/set-op root, forbidden-node walk, function deny-list, schema allow-list, numeric LIMIT, cap 501.
29. *Why AST not regex?* → `WITH x AS (DELETE … RETURNING *) SELECT …`.
30. *Layers stopping writes?* → prompt, AST, role check, SELECT-only role, READ ONLY txn, timeouts, row cap.
31. *Repair?* → One retry with SQL + DB error, only for execution errors.
32. *NL summary of SQL results?* → NOT IMPLEMENTED.
33. *How are SQL passwords stored?* → Fernet, write-only, key env or 0600 file.
34. *Upload validation?* → extension, MIME, magic bytes, size (411/413/415).
35. *Path traversal?* → display name only; UUID keys; resolved path must stay in root.
36. *Malformed PDF hangs?* → Child process killed after 120 s.
37. *Worker reliability?* → `SKIP LOCKED`, heartbeats, stale recovery, backoff, one-transaction commit.
38. *Why Postgres as queue?* → One store, transactional state; tiny throughput.
39. *Why sync endpoints?* → psycopg async + Windows Proactor; single-user.
40. *Concurrency control?* → One generation at a time; 10 s wait → 429.
41. *Error handling?* → `AppError` envelope; no stack traces; 503 for DB/model availability.
42. *Logging privacy?* → ids/counts/timings only; key + pattern redaction.
43. *Metrics: define MRR and nDCG.* → see §5.
44. *Why no LLM judge?* → Deterministic, reproducible, free; faithfulness left NOT MEASURED.
45. *Evaluation weaknesses?* → 50 synthetic unreviewed cases; wording reuse; tiny test split.
46. *Retrieval vs generation failure?* → Separate metrics + candidate ranks + failure categories.
47. *Biggest failure found?* → Superseded handbook cited (24 vs 26 days) despite both retrieved.
48. *Production bug found live?* → Keep-alive race → ECONNRESET → 500; `--timeout-keep-alive 75`.
49. *Scale to 100k docs?* → more workers, typed vectors + HNSW, object storage, GPU inference, measure recall.
50. *Your contribution?* → Specs, decisions, direction and verification of an AI-agent build; can explain every part.

## 9. Last-minute notes

- Say "on this 50-question synthetic set" every time you quote a number.
- Say "I built it with an AI coding agent" before anyone asks; then show depth.
- Default Ask mode is **dense**; hybrid measured better — mention as the first improvement.
- CI is configured but has **never run** on GitHub.
- S4 reranker, faithfulness, RAM, tokens/s: **NOT MEASURED**.
- No auth; single default workspace; no OCR; no streaming; no multi-turn context.
- Start the Azure VM 10 minutes before; stop it after.
