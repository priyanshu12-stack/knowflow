# KnowFlow — Interview Presentation Kit

> Spoken scripts, demo order and what to show when. Everything said here is backed by the code and
> by `docs/evaluation/README.md` (commit `65af69c`). Read the "honesty rules" once; they matter more
> than polish.
>
> Companion: [Master guide](KNOWFLOW_ENGINEERING_AND_INTERVIEW_MASTER_GUIDE.md) ·
> [Quick revision](KNOWFLOW_QUICK_REVISION.md) · [Question bank](KNOWFLOW_INTERVIEW_QUESTION_BANK.md)

## Honesty rules (non-negotiable)

1. **Authorship.** Built solo, with an AI coding agent, from your own specs (58 of 60 commits are
   co-authored by Claude). Say "I designed and built it with an AI coding agent; I wrote the specs,
   made the decisions, verified everything and can explain any part" — never "I hand-wrote all of it".
2. **Numbers.** Always say "on a 50-question synthetic set that hasn't been human-reviewed".
3. **Status.** Release candidate; no production users; the Azure deployment is on demand and
   password-protected.
4. **Gaps.** Reranker not measured; no auth; CPU answers take ~a minute; CI configured but not yet run
   on GitHub.

## Before the interview (checklist)

- [ ] `./deploy/azure/knowflow-azure.ps1 start` about 10 minutes before; open
      `https://knowflow-priyanshu.centralindia.cloudapp.azure.com`, log in.
- [ ] Overview page: all checks green.
- [ ] Ask one warm-up question (loads the model; first answer is slower).
- [ ] Tabs ready: Overview · Ask KnowFlow · SQL Analyst · Evaluation Lab · GitHub repo ·
      `docs/evaluation/README.md` · `apps/api/app/modules/rag/answer.py` ·
      `apps/api/app/modules/sql_assistant/validation.py` · the architecture diagram (master guide B.1).
- [ ] Fallback if the VM or network fails: local run, or the screenshots in `docs/screenshots/`.
- [ ] After: `./deploy/azure/knowflow-azure.ps1 stop`.

**Latency plan:** an answer takes ~45 s on the VM. Never wait in silence: while it generates, explain
what's happening ("it's embedding the question, searching pgvector, and now the 4B model is writing a
JSON answer on CPU"), then point at the stage timings in the answer's trace.

---

## 30-second pitch

"KnowFlow is a local-first AI knowledge workspace. You upload documents and ask questions, and every
answer comes with citations that are checked against the passages actually retrieved — if nothing
supports an answer, it says so instead of guessing. It also turns business questions into safe,
read-only SQL, and it asks what a vague term like 'best customer' means before writing the query.
It runs entirely on open-source models through Ollama, with PostgreSQL and pgvector as the only
database, and it has an evaluation lab that measures retrieval quality with standard metrics."

## 1-minute explanation

"KnowFlow solves three problems with typical document chatbots: they make things up, they send your
data to someone else's API, and nobody measures whether they're any good.

Documents go through a background worker that validates them, extracts text in a sandboxed process,
splits them into passages two different ways and embeds them with a local model. When you ask a
question, it retrieves passages with vector search, keyword search, or both fused with Reciprocal Rank
Fusion. A local Qwen 4B model has to answer in JSON, and I verify every citation number against the
passages it was actually given — anything invalid is removed, and an answer with no valid citation is
refused.

For SQL, the generated query is parsed into a syntax tree with SQLGlot; only a single SELECT on
allowed schemas gets through, and it runs under a read-only role with a timeout and a row cap.

On my 50-question test set, hybrid retrieval beat dense-only on every metric, and the model made the
right answer-or-refuse decision on all 12 held-out questions."

## 3-minute technical explanation

**(0:00) Problem.** "I wanted a document assistant I could trust: answers tied to sources, data that
stays on my machine, and quality I can measure. The constraint was a 7.3 GB laptop with no GPU and a
zero budget."

**(0:25) Architecture.** *(show diagram)* "It's a Next.js front end that only talks to its own server,
which proxies to a FastAPI backend. A separate worker process does ingestion and evaluation, using a
PostgreSQL table as the job queue — workers claim jobs with `FOR UPDATE SKIP LOCKED`. PostgreSQL also
holds the text, a generated full-text-search column and the pgvector embeddings. Ollama runs Qwen3 4B
for generation and nomic-embed-text for 768-dimensional embeddings."

**(1:00) Ingestion.** "Uploads are checked four ways — extension, MIME, the file's real signature and
size — and stored under generated names. Text extraction runs in a child process with a timeout, so a
hostile PDF can't hang the worker. Each document is chunked two ways, fixed windows with overlap and a
structure-aware recursive split, so I can compare them. Sections, chunks, vectors and the 'ready'
status are written in one transaction."

**(1:35) Answering.** "Retrieval can be dense, keyword or hybrid. Postgres full-text search ANDs every
term, which found nothing for natural questions, so I OR the stemmed terms and rank by cover density.
The answer prompt marks the passages as untrusted data. The model must return JSON; I validate it with
Pydantic, keep only citation numbers that point to real passages, and refuse answers with none."

**(2:10) SQL.** "Ambiguous terms are caught from a glossary before any model call, so 'best customers'
gets a clarifying question instantly. Generated SQL is validated on its syntax tree — including a
DELETE hidden in a CTE — and executed read-only with a 5-second timeout and a 500-row cap."

**(2:35) Results and honesty.** "Hybrid scored MRR 0.891 versus 0.879 for dense-only; abstention was
12 for 12 on the held-out split. The set is small and synthetic, so I treat that as evidence the
pipeline works, not a quality claim. A real failure I found: with two handbook versions, the model
cited the older one even though retrieval found both — that's what I'd fix next."

## 5-minute walkthrough (with demo)

| Time | Say | Show |
|---|---|---|
| 0:00–0:30 | **Opening and problem.** "Most 'chat with your documents' tools have three problems: they hallucinate, they send your data to a third party, and nobody measures them. KnowFlow is my answer to all three, on a laptop with no GPU and no budget." | Nothing (eye contact) |
| 0:30–1:00 | **What it is.** "This is the overview. Everything you see is running on one machine: PostgreSQL with pgvector, Ollama with two local models, and a background worker. If something were missing, this page would show the exact command to fix it." | **Overview** (all green) |
| 1:00–2:15 | **RAG demo.** Type *"What is the hotel cap per night?"* (Semantic). While waiting: "It embeds the question, runs a cosine search in pgvector, and the 4B model writes a JSON answer on CPU — that's why it takes about half a minute." When it arrives: "Here's the answer with citation 1 — clicking it opens the exact passage and section." Then: "If I ask something the documents don't cover…" type *"What is the capital of Mongolia?"* → "it refuses instead of guessing." | **Ask KnowFlow** → click `[1]` → source drawer; then the refusal |
| 2:15–3:15 | **SQL demo.** Type *"Who were our best customers last month?"* → "It didn't call the model — the glossary says 'best customer' is ambiguous, so it asks." Pick *Highest paid revenue*. "Now it generates SQL, validates the syntax tree, and runs it read-only with a timeout and a row cap. You can see the exact query, the tables and its assumptions." | **SQL Analyst**: clarification panel → SQL + results |
| 3:15–4:00 | **Evaluation.** "I didn't want to judge retrieval by feel. On a 50-question gold set, hybrid beat dense-only on every metric — MRR 0.891 versus 0.879 — and lexical alone was even stronger here because the questions reuse the documents' wording, which tells me the set needs paraphrases." | **Evaluation Lab** comparison, or the README table |
| 4:00–4:40 | **Challenges and decisions.** "Three decisions I'd defend: PostgreSQL for everything, so a document is never half-indexed; verifying citations instead of trusting the model; and five independent layers of SQL safety. The hardest bug came from running it live: the Next.js proxy and Uvicorn disagreed on keep-alive timing, which caused random 500 errors. I found it in an end-to-end check and fixed it." | Optional: `verify_citations` code |
| 4:40–5:00 | **Conclusion.** "It's a release candidate with 390 automated tests, deployed on an Azure student VM I start for demos. Next I'd fix how it handles conflicting policy versions, run the reranker experiment, and get the test questions reviewed by a person." | GitHub repo |

**If the live demo fails:** "The VM is on student credit, so I keep it off; here are screenshots from
the same flows" → `docs/screenshots/ask-citation.png`, `sql-clarification.png`, `sql-result.png`,
`evaluation-lab.png`.

## 10-minute deep technical presentation

1. **(0:00–1:00) Problem and constraints** — same as 5-minute opening, plus: "single user, local,
   7.3 GB RAM, CPU only, zero recurring cost — written into an ADR and enforced by a CI check that
   fails on paid-API SDKs."
2. **(1:00–2:30) Architecture** *(diagram)* — browser → Next.js proxy (no CORS, 600 s timeout) →
   FastAPI (thin routers, services, protocols for models) → worker with a Postgres job queue (`SKIP
   LOCKED`, heartbeats, exponential backoff, stale-job recovery) → PostgreSQL (22 tables, generated
   `tsvector`, GIN index, pgvector) → Ollama. Explain why there's no Redis and no vector DB.
3. **(2:30–4:00) Ingestion in detail** — four-way validation (show `evil.pdf` story: an executable
   renamed to .pdf is rejected by its magic bytes), child-process extraction with timeout, page and
   heading metadata, two chunkers, embedding with nomic's task prefixes and a probed dimension,
   one-transaction completion.
4. **(4:00–5:45) Retrieval and answers** — dense SQL (cosine `<=>`, scoped by embedding version,
   workspace, strategy, ready status); the FTS OR-of-lexemes fix; RRF with a worked example
   (A: dense 1 + lexical 3 → 0.0323 beats C: lexical 1 only → 0.0164); weak-evidence gate (dense only);
   prompt with untrusted `<source>` blocks; JSON schema + Pydantic; citation verification and the four
   abstention reasons. Show `rag/answer.py::verify_citations`.
5. **(5:45–7:00) Text-to-SQL** — glossary clarification with no model call; read-only role check;
   introspection with FK join hints; prompt `sql-v3` at temperature 0; SQLGlot validation (show the
   CTE-DELETE example); READ ONLY transaction, statement and lock timeouts, 501-row fetch; one repair.
   Show `validation.py::validate_sql`.
6. **(7:00–8:30) Evaluation** — evidence matchers instead of chunk ids (labels survive re-indexing);
   dev/test split; metric definitions; the results table; what they do and don't show; failure analysis
   (q24 labelling limitation, q38 real citation error, the 24-vs-26-days conflict observed live).
7. **(8:30–9:30) Reliability and deployment** — error envelope with request ids; log redaction;
   generation gate (429 instead of overload); readiness that distinguishes busy from down; Azure VM
   with Caddy, HTTPS and basic auth, stop/start to save credit; the keep-alive bug found in the
   end-to-end check.
8. **(9:30–10:00) What's next** — default to hybrid, conflict handling + re-measure, S4 reranker,
   human-reviewed and larger gold set, auth, streaming.

## Explaining the architecture (when they say "draw it")

Draw five boxes left to right: **Browser → Next.js → FastAPI → PostgreSQL**, with **Ollama** below
FastAPI and a **Worker** box below PostgreSQL that also talks to Ollama. Then say:

"The browser only talks to Next.js, which proxies `/api/v1`. FastAPI does request validation, the
SQL Analyst and question answering. Anything slow — extraction, embedding, evaluation runs — is a row
in a Postgres jobs table that the worker claims. PostgreSQL is the only store: documents, chunks,
full-text index and vectors, so a document becomes searchable in one transaction. Ollama serves the
two local models."

## Results to quote (exact)

- Retrieval (50 cases, K = 5): S1 fixed+dense MRR 0.837 / nDCG 0.873; S2 recursive+dense 0.879 / 0.891;
  **S3 hybrid 0.891 / 0.905**; lexical-only 0.901 / 0.918; S4 NOT MEASURED.
- Retrieval latency p50 ~40 ms (mostly embedding the question).
- Answers on the held-out split (12): abstention 12/12; citation precision 0.955 (n = 11); latency
  p50 57 s / p95 138 s on the laptop.
- Safety probes (7): abstention 7/7; injection resisted 1/1.
- Tests: 282 backend (+3 opt-in skipped), 80 frontend unit, 28 Playwright.

## Technical challenges to tell as stories

1. **Keyword search found nothing** → OR of stemmed lexemes + cover-density ranking → hybrid became
   the best dense-based strategy.
2. **SQL safety** → why regex fails (DELETE inside a CTE) → AST + four more layers.
3. **7.3 GB, no GPU** → one generation at a time, long explicit timeouts, readiness reports "busy"
   rather than "down".
4. **Live-only bug** → keep-alive race between the proxy and Uvicorn → found by an end-to-end check,
   fixed, re-verified.
5. **A failure I haven't fixed yet** → conflicting handbook versions → retrieval right, generation
   wrong → the plan to fix and measure it.

## Closing statement

"What I'd like you to take away is how I work: I treat the model's output as untrusted input, I
measure before I claim, and I write the limitations next to the results. KnowFlow is small, but every
part of it — from a PDF's bytes to a cited answer or a read-only SQL result — is something I can explain,
test and improve. I'd be glad to go deeper into any part."
