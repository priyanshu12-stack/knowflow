# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows SemVer once a release is tagged (PRD §11: only after acceptance checks).

## [Unreleased]

### Added
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
