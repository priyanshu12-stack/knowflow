<!-- Generated from KnowFlow_PRD_Product_Requirements.docx (authoritative source). Do not edit by hand. -->
KNOWFLOW
# Product Requirements Document
What KnowFlow is, who it serves, user journeys, features, delivery phases and acceptance tests

| DOCUMENT CONTROL | VALUE |
|---|---|
| Document ID | PRD-001 |
| Version | 1.0 |
| Status | Baseline specification – update decisions in the repository |
| Product | KnowFlow – Local-first Enterprise Knowledge Intelligence |
| Owner | Solo developer / project maintainer |
| Date | 06 November 2026 |


## How to use this document
Give this document to the coding agent as an authoritative project specification. The agent must read all three documents (TRD, PRD and DRD) before changing code. If two documents appear to conflict, use the priority rules in the PRD and record the resolution in docs/decisions/ rather than silently inventing a design.
Important: this specification defines the intended product and acceptance criteria. It does not claim that implementation, benchmark results, security certification or deployment already exist.

## 1. Product summary
KnowFlow is a local-first enterprise knowledge intelligence workspace. It helps a user ask trustworthy questions across documents and structured business data. It retrieves evidence, answers with verifiable citations, asks clarification when a question is ambiguous, and provides a measurable evaluation workbench so the developer can prove whether changes improve quality.

| Product element | Definition |
|---|---|
| Product name | KnowFlow |
| Tagline | Answers grounded in your knowledge. |
| Primary user | A student/developer, researcher, analyst or small team who wants private, locally run document intelligence. |
| Core problem | Document collections are difficult to search; generic chatbots may retrieve irrelevant passages, hallucinate, hide uncertainty and cannot safely interpret business questions. |
| Value proposition | Private local inference, evidence-first answers, transparent retrieval, measurable quality and safe natural-language-to-SQL. |
| Differentiator | A RAG evaluation lab is part of the product, not an afterthought. Users can compare retrieval configurations and see why an answer was produced. |


## 2. Product goals and non-goals

### 2.1 Goals
- Let a user create a workspace and build a searchable knowledge library from supported documents.
- Return concise answers with citations that open the exact source page/section.
- Say 'I could not find sufficient evidence' when retrieval is weak.
- Allow the user to compare chunking and retrieval strategies on a fixed evaluation dataset.
- Support natural-language questions over a connected SQL database, including clarification of ambiguous terms.
- Run core inference locally without paid model APIs.
- Deliver a polished, responsive interface and reproducible local setup.
- Make technical decisions and measured trade-offs visible in the repository.

### 2.2 Non-goals for v1
- A general-purpose ChatGPT clone or autonomous agent that can do arbitrary tasks.
- Training or fine-tuning foundation models.
- OCR-heavy scanned document processing, image/audio/video RAG.
- Writing to customer databases or executing arbitrary SQL.
- A public multi-tenant SaaS with billing, SSO or enterprise admin.
- Guaranteeing perfect answers or a preselected accuracy percentage.
- Requiring a paid hosted LLM, embedding or reranking API.

## 3. User personas and key jobs

| Persona | Need | Success looks like |
|---|---|---|
| Student / researcher | Search notes, papers and project documents; cite sources. | Finds the exact passage and can verify the answer quickly. |
| Business analyst | Ask questions over reports and a sample sales database. | Gets correct metrics, SQL explanation and clear clarification when terms are ambiguous. |
| Solo developer / evaluator | Understand whether RAG changes actually improve quality. | Runs a repeatable benchmark and compares metrics by configuration. |


## 4. Product information architecture

| Navigation item | Purpose | Primary screen contents |
|---|---|---|
| Overview | Workspace landing and system health | Document count, recent activity, ingestion status, model readiness, recent evaluation run. |
| Knowledge Library | Manage source documents | Upload area, document table, status, file type, pages, chunks, delete/retry, filters. |
| Ask KnowFlow | Evidence-grounded chat | Conversation list, question composer, answer, citation panel, retrieval details, feedback. |
| SQL Analyst | Ask questions about structured data | Connection selector, schema browser, query prompt, clarification cards, SQL preview, results table. |
| Evaluation Lab | Benchmark retrieval and answer quality | Dataset manager, configuration selector, run history, metric cards, comparison charts, per-case inspection. |
| Models & Settings | Local runtime configuration | Ollama status, generation model, embedding model, reranker toggle, model validation, resource warnings. |
| Activity / Logs | Troubleshooting and traceability | Ingestion jobs, failed jobs, request ids, safe logs and latency. |


## 5. Functional requirements

### 5.1 Workspace and onboarding
- On first launch, show a short setup checklist: database connected, Ollama reachable, generation model available, embedding model available.
- Create a default local workspace automatically; allow rename. Avoid forcing account registration in local v1.
- Provide a guided sample dataset option using public-domain or synthetic documents. Label sample content clearly.
- Show exactly which models are downloaded/required and their approximate disk footprint where available.
- Never imply that an optional reranker is required for basic RAG.

### 5.2 Knowledge Library and ingestion
- Support PDF (text-based), DOCX, TXT and Markdown in v1. CSV may be accepted as a later structured-document feature; scanned PDF OCR is out of scope.
- Allow drag-and-drop and file picker. Show allowed formats and maximum file size before upload.
- Show each document's state: queued, extracting, chunking, embedding, ready, failed.
- Display document name, type, size, upload date, page count, chunk count and last error in plain language.
- Allow retry failed ingestion and delete a document with confirmation.
- Prevent duplicate confusion by detecting identical SHA-256 content and offering skip/re-index/new version choices.
- Preserve page numbers and section headings for citations. If page extraction is unavailable, state that citation granularity is section/document level.

### 5.3 Ask KnowFlow – RAG chat
- User can ask a question across all ready documents or select specific documents.
- Answer should be direct, readable and proportionate to the question; include inline numbered citations.
- Each citation opens a source drawer with document name, page/section, and the exact supporting excerpt.
- Show a compact 'Sources used' area and optional 'How this was found' panel with retrieval strategy and candidate count.
- If no evidence is found, abstain and explain what source or detail is missing.
- If sources conflict, present the conflict and cite both; do not silently choose one.
- Support conversation history and rename/delete conversations.
- Allow helpful/not helpful feedback and optional reason. Feedback is stored for error analysis.
- Do not claim that the model 'read all documents'; disclose that it retrieved a limited set of passages.

### 5.4 Evaluation Lab
- Create/import evaluation datasets from CSV or JSONL with question, reference answer and expected relevant chunk/document ids.
- Include a small sample dataset with synthetic/public content and a guide for building a manually verified 50–150 question dataset.
- Select chunking strategy, retrieval strategy, top-k, RRF setting, reranker on/off, model and prompt version.
- Run a benchmark asynchronously and show progress.
- Compare runs side-by-side using Recall@K, Precision@K, MRR/nDCG, faithfulness (if judge enabled), answer correctness, citation accuracy, abstention accuracy and latency.
- Allow opening a test case to inspect expected evidence, retrieved chunks, generated answer and failure category.
- Export a CSV/JSON report with configuration and dataset version.
- Clearly label judge-based metrics as model-judged estimates and support manual review.

### 5.5 SQL Analyst
- Ship a synthetic demo database with customers, orders, order_items, payments and products tables plus a visible glossary.
- Allow user to configure one local PostgreSQL connection with write-only secret entry; credentials are never returned to frontend.
- Show the allowed schema and table/column descriptions before asking questions.
- Detect ambiguity in business language. Example: 'best customer' must ask whether this means highest paid revenue, most orders or most recent activity, unless a glossary definition is configured.
- Show clarification options and require explicit user choice.
- Show generated SQL and plain-English explanation before execution, with a Run button if the product is configured for manual execution. For v1, execution can occur after validation but must be clearly previewed and read-only.
- Display results in a sortable table with row cap and query duration.
- Show safe failure messages for unsupported or rejected queries; never attempt a destructive query.

### 5.6 Model settings and diagnostics
- Show Ollama connection status and available local models.
- Allow selecting a generation model and embedding model from locally installed, compatible models.
- Validate model availability, response schema and embedding dimension before saving settings.
- Changing embedding model must warn that all indexed vectors need re-embedding.
- Reranker is an optional toggle with a resource warning.
- Show a setup guide with commands such as `ollama pull qwen3:4b`, `ollama pull nomic-embed-text` and optional reranker installation.

## 6. User journeys / end-to-end flows

### Journey A – first-time user to first cited answer
- Open KnowFlow. Overview checks PostgreSQL and Ollama readiness.
- If models are missing, show exact local setup instructions and a re-check action.
- Open Knowledge Library and upload a PDF or DOCX.
- See progress from queued to extracting, chunking, embedding and ready.
- Open Ask KnowFlow and ask a question about the uploaded file.
- Read the answer and click citation [1]. The source drawer opens at the cited page/section.
- If the answer is unsupported, the system abstains and suggests a better-scoped question.

### Journey B – improve retrieval quality
- Open Evaluation Lab and create/import a dataset of manually verified questions.
- Run the baseline fixed/recursive + dense retrieval configuration.
- Run hybrid retrieval with dense + lexical + RRF.
- Run hybrid + reranker.
- Compare retrieval metrics and latency on the same dataset version.
- Inspect failed cases, record a decision in docs/decisions/ and select the best measured configuration.
- Export report and include reproducible configuration in README.

### Journey C – ambiguous Text-to-SQL
- Select the demo sales database.
- Ask: 'Show me our best customers last month.'
- KnowFlow identifies ambiguity and asks whether 'best' means highest paid revenue, most orders or highest average order value.
- User selects highest paid revenue.
- KnowFlow generates SQL, validates it and executes with read-only role and limits.
- Show SQL, result table, date range and plain-English explanation.
- If SQL is rejected or times out, explain the reason and allow a revised question.

## 7. Delivery plan: milestone-by-milestone
Build in small vertical slices. At the end of every milestone, the application must still start and existing tests must pass. Do not implement all backend modules first and postpone the UI.

| Milestone | Work to complete | Exit criteria |
|---|---|---|
| M0 – Repository foundation | Create repository, README, docs, issue/PR templates, .gitignore, .env.example, branch strategy, lint/format configs, initial Next.js and FastAPI skeleton, Docker Compose for Postgres/pgvector. | Clean clone starts web, API and DB; health checks pass; no secrets committed. |
| M1 – Data foundation | SQLAlchemy models, Alembic migrations, workspace/document/job tables, filesystem storage service, upload API and library UI. | Upload PDF/DOCX/TXT/MD, metadata persists, duplicate checksum handled, file stored safely. |
| M2 – Ingestion pipeline | Text extraction, page/heading metadata, fixed and recursive chunking, job worker, failure/retry state, chunk inspection. | Uploaded file becomes searchable chunks; job restart and failure states tested. |
| M3 – Local model integration | Ollama health, model adapter, Nomic embedding adapter, dimension probe, embedding batches and pgvector storage. | Embeddings generated locally; missing model gives actionable instructions; no external API. |
| M4 – Basic RAG | Dense retrieval, context packing, prompt versioning, Qwen generation, Pydantic response, citations and abstention. | User asks a question and receives grounded answer with clickable source citation. |
| M5 – Retrieval experiments | Postgres FTS, RRF, top-k controls, reranker adapter/toggle, dataset import, retrieval metrics and comparison UI. | Four configurations can run on same gold set and produce reproducible metrics. |
| M6 – Text-to-SQL | Demo schema, schema introspection, glossary, ambiguity detection, clarification state, SQL generation, SQLGlot validation, read-only execution. | Ambiguous question asks clarification; unsafe SQL is rejected; safe SELECT returns table. |
| M7 – Product polish and safety | Prompt-injection tests, workspace filters, file limits, secret redaction, audit events, empty/loading/error states, responsive design, accessibility. | Security and UX acceptance tests pass; no major dead-end screens. |
| M8 – Release and deployment | Docker Compose, production build, migrations, health checks, seed demo, CI, docs, demo video, evaluation report and release tag. | A new machine can follow setup docs and run the product locally; CI green. |


## 8. What to build first vs later

| Priority | Feature |
|---|---|
| P0 – Must ship | Local setup; document upload/ingestion; dense RAG; citations; abstention; evaluation dataset + baseline metrics; hybrid search; SQL clarification + safe read-only execution; tests; Docker Compose; README. |
| P1 – Strong differentiators | Reranker comparison; semantic chunking experiment; per-case evaluation explorer; citation verification; model benchmarking; detailed latency/resource dashboard; conversation history. |
| P2 – Only after stable v1 | Streaming chat; multi-workspace collaboration; OCR; advanced table extraction; multi-agent workflows; external hosted deployment; SSO; advanced permissions. |


## 9. Quality requirements and acceptance checklist

| Area | Acceptance test |
|---|---|
| Functional | A user can upload a supported file, see ingestion progress, ask a question and open a valid citation. |
| Grounding | Every factual answer claim that relies on documents is tied to one or more retrieved citations; unsupported question abstains. |
| Retrieval | The same evaluation dataset can run across dense, hybrid and reranked modes; report includes configuration and sample count. |
| SQL safety | Ambiguous 'best customer' asks clarification; UPDATE/DELETE/DDL/multiple statements and unapproved tables are rejected. |
| Privacy | No file content or secret is sent to external inference APIs; local model runtime is the default and only required provider. |
| Reliability | Failed ingestion is visible and retryable; duplicate uploads are handled; app survives worker restart. |
| Performance | Large tasks run asynchronously; UI shows progress; request timeouts and concurrency caps exist. |
| Accessibility | Keyboard navigation, visible focus, labels, contrast and reduced-motion preference are supported. |
| Deployment | Fresh clone can follow README and start using documented local commands; migrations and seed data work. |
| Maintainability | Typed contracts, modular services, tests, linting, migration history and ADRs exist. |


## 10. Dataset and demo content policy
- Use synthetic data for the SQL demo. Seed enough rows and edge cases to test ambiguity, date filters, refunds, duplicate names and nulls.
- Use public-domain or appropriately licensed sample documents for the public demo. Track source URL and license in docs/demo-data-sources.md.
- Do not upload private college, employer, customer or medical documents to a public demo.
- Evaluation reference answers and relevant chunk labels must be manually checked. Store dataset version and label author/date.
- Include unanswerable questions and malicious prompt-injection examples; measure abstention and resistance.

## 11. Release checklist
- README includes problem, screenshots, architecture, quick start, model download commands, configuration, API docs, evaluation results and limitations.
- TRD, PRD and DRD are stored in docs/ and match the implemented product.
- Architecture diagram and at least 3 ADRs are committed.
- No `.env`, secrets, model weights, uploads, DB volumes, generated logs or private evaluation corpora are tracked.
- Unit/integration/e2e tests pass; CI is green.
- Migrations run from empty DB and upgrade from previous release.
- Demo seed is reproducible and clearly synthetic/public.
- Evaluation report includes dataset size, model tag, machine specs, strategy, metrics and run date.
- Known limitations and future work are stated honestly.
- Release is tagged only after acceptance checks.

## 12. Coding-agent execution and Git discipline
The coding agent must act as an implementation assistant, not a one-shot code generator. It must inspect the repository before editing, plan one milestone, implement a small slice, run checks, summarize the diff and commit only coherent working changes.
- Before coding: inspect git status, current branch, remotes, existing files and all three specification documents. Never overwrite existing user work.
- Create a feature branch per milestone (e.g. feat/m1-document-upload). Keep main branch stable.
- Use conventional commits: feat:, fix:, test:, docs:, refactor:, chore:. Each commit should represent a meaningful verified unit.
- Do not create fake backdated commits, artificial author identities, or commits claiming work that was not performed.
- After each commit, show commit hash, changed files, tests run and test outcomes. Ask before pushing if credentials/remote permissions are not already configured.
- Never force-push, rewrite history or push directly to a protected main branch. Do not commit secrets, model files or data.
- If a test fails, fix it or clearly report the blocker; do not hide or skip the test to create a green commit.
- If the agent session ends, resume from git status, latest commit and docs/implementation-status.md rather than restarting or repeating completed work.

## 13. Definition of done
KnowFlow v1 is done when a new developer can clone the repository, install the documented local prerequisites, start the app without paid API keys, ingest sample documents, ask evidence-grounded questions with citations, run and compare retrieval evaluations, safely query the synthetic SQL database with clarification, inspect errors and metrics, and reproduce the documented test/evaluation results. A polished screenshot without working flows is not done.
