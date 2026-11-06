# ADR-006: Text-to-SQL safety, clarification and secrets

- Status: Accepted (M6)
- Milestone: M6

## Context

TRD §6.3 and §10 require clarification before ambiguous SQL, AST validation (not regex), a SELECT-only
role, a statement timeout, a row limit, schema allow-lists, and write-only secrets. The generation model
is `qwen3:4b` on CPU, which TRD §4.1 warns may be weak at SQL.

## Decision

**Isolation.** The demo lives in its own database (`knowflow_demo`, schema `sales`, synthetic data)
with its own login role, `knowflow_reader`. That role has LOGIN only (no superuser, createdb,
createrole, inherit or replication), CONNECT on the demo database, USAGE on `sales`, and SELECT on
its tables. It also has `default_transaction_read_only = on` and a `statement_timeout`. The seeder revokes
PostgreSQL's default PUBLIC `CONNECT`/`TEMPORARY` on the application database, so the reader can't
even open it.

**Verified on the reference machine (2026-11-07), as the reader role:**

| Attempt | Result |
|---|---|
| INSERT / CREATE TEMP / CREATE in public | blocked: "cannot execute … in a read-only transaction" |
| The same after `SET default_transaction_read_only = off` | blocked by grants: "permission denied for table / schema", "permission denied to create temporary tables" |
| `pg_sleep(7)` | cancelled by the statement timeout |
| Connect to the application database | `FATAL: permission denied` |

**Layers, in order** (each one alone would stop a destructive query):

1. *Clarification first.* Glossary terms marked `ambiguous` (e.g. "best customer": paid revenue / most
   orders / average order value) are detected deterministically, with plurals and synonyms. The answer is
   a clarification object: no model call, no SQL, nothing executed. The model can also return its own
   clarification (2–4 options) for ambiguity the glossary doesn't cover.
2. *Generation.* There's one structured call (`sql-v3`): the allow-listed schema (names, types, comments, FK join
   hints), the definitions in force (including the user's choice) and today's local date. The model
   never sees credentials or data rows.
3. *SQLGlot AST validation:* exactly one statement; root SELECT or set operation; no write, DDL,
   transaction, lock, `SELECT INTO`, COPY, SET or unknown-command nodes anywhere (CTEs included); tables
   must be CTEs or live in allow-listed schemas; no system catalogs or cross-database names; a
   denylist of dangerous functions (`pg_sleep`, file / large-object access, `dblink`, settings, backend
   control, sequences); LIMIT must be a literal; rows are capped at `SQL_MAX_ROWS + 1`. 45 unit tests
   cover these cases.
4. *Execution:* re-check that the role is read-only, then `SET TRANSACTION READ ONLY` plus
   `SET LOCAL statement_timeout` / `lock_timeout`. Results are fetched up to the cap, then rolled back.
5. *Reporting:* rejected SQL is shown with the reason and is never run. Database errors on validated SQL
   (e.g. a misspelled column) can be sent back to the model **once, at the user's request** ("Ask the
   model to fix this query"), and the fix is validated again.

**User connections:** `POST /sql/connections/test` connects, refuses superusers and roles with
INSERT/UPDATE/DELETE on any allow-listed table, and requires visible tables. Only then does it save.
Passwords are encrypted with Fernet. The key comes from `SECRET_KEY` or an auto-generated
`data/secret.key` (gitignored, created with mode 0600). No API response contains the password or
its ciphertext. This resolves ADR-000 G-4.

**History:** every turn is stored in `sql_queries` with its status and safety decision. String
literals in the stored SQL are redacted.

## Consequences / measured behaviour

- Journey C ("Show me our best customers last month.") works end to end with the real model: a clarification
  first, then after "Highest paid revenue" a correct CTE query for October 2026. Its top-5 output
  matched a hand-written query exactly. Generation took ~70 s on CPU; execution took 41 ms.
- Before prompt v3, `qwen3:4b` misspelled identifiers (`net_reasult`, `ranked_custom`), and one repair
  output came back truncated. Every one of those failed safely (a database error, or a parse rejection before
  execution). Prompt v3 adds FK join hints, a worked example and a larger output budget. A
  larger model (`qwen3:8b`) on a 16 GB machine should be benchmarked before claiming SQL accuracy.
- There's no SQL accuracy benchmark yet: `evaluation_cases.expected_sql` exists, but no SQL gold set
  has been written. That's NOT MEASURED.
