# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows SemVer once a release is tagged (PRD §11: only after acceptance checks).

## [Unreleased]

## [1.0.0-rc.1] - 2026-11-07

Release candidate. Every milestone M0–M8 is implemented and verified locally. Before 1.0.0: CI must run (it needs a GitHub remote), a demo video must be recorded, and a person must review the gold set.

### Added
- M1 Knowledge Library: upload with extension/MIME/signature/size checks, duplicate handling (skip / re-index / new version), safe storage, delete.
- M2 ingestion worker: PDF pages / DOCX headings / Markdown sections, fixed and recursive chunking, Postgres full-text search, retries, stale-job recovery, chunk inspection drawer.
- M3 local models: Ollama adapters, probed embedding versions, batched pgvector storage, Models & Settings with real validation probes.
- M4 Ask KnowFlow: grounded answers with verified citations, abstention, source drawer, conversations, feedback.
- M5 Evaluation Lab: hybrid RRF retrieval, optional reranker, gold-set import, deterministic metrics, resumable runs, comparison table, per-case inspector, export; synthetic sample corpus and a 50-case gold set.
- M6 SQL Analyst: synthetic demo database with a SELECT-only role, glossary clarification, SQLGlot validation, read-only execution, encrypted write-only connection secrets.
- M7 safety and polish: audit events, Activity and Help pages, Overview metrics, value-based log redaction, a workspace-isolation sweep, Playwright smoke suite.
- M8: README with real screenshots, evaluation report, updated traceability matrix, demo data sources, dataset guide.

### Fixed
- Next.js proxy timeout (30 s default) dropped answers generated on the CPU.
- Readiness reported Ollama as down while it was busy generating.
- Lexical search ANDed every term and matched nothing for natural questions.
- `db.ps1 start` failed when PostgreSQL was already running.

### Added (M0)
- Project specifications (TRD, PRD, DRD) as Markdown in `docs/`, regenerated from the `.docx` sources by `scripts/specs_to_md.py`.
- Requirements traceability matrix, implementation roadmap, and ADR-000, ADR-001 (proposed), ADR-007 and ADR-008.
- M0 foundation:
  - FastAPI service with env-validated settings, structured JSON logs with request IDs and secret redaction, a consistent error envelope, and `GET /api/v1/health/live` and `/ready` (separate PostgreSQL, pgvector, Ollama and model checks with setup commands).
  - Next.js 16 web app with the DRD design tokens, app shell (sidebar, top bar, mobile drawer), and an Overview showing live system readiness.
  - Native PostgreSQL 16 + pgvector scripts (`scripts/db.ps1`), Docker Compose for Docker hosts, `scripts/dev.ps1` and a Makefile.
  - GitHub Actions CI, the zero-paid-API guard (`scripts/check_no_paid_apis.py`), and issue/PR templates.
  - Docs: design system, branch strategy, architecture overview, evaluation policy.

### Fixed
- PowerShell scripts failed (`setup`) or hung (`pg_ctl start`) when their output was redirected. Both were found by the fresh-clone check.
