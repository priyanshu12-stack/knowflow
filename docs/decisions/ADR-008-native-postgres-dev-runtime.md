# ADR-008: Native PostgreSQL via conda on the development machine

- Status: Accepted by project owner (2026-11-06)
- Milestone: M0

## Context

TRD §3 and §13 specify Docker Compose for PostgreSQL + pgvector. The development machine has no Docker,
7.3 GB of RAM (~0.8 GB free), and Windows 11 Home. Docker Desktop with WSL2 typically reserves 2 GB+,
which would compete with the local LLM (`qwen3:4b`).
`conda-forge` publishes `postgresql` and `pgvector` (0.8.6) builds for win-64, and Anaconda is already installed.

## Options considered

1. Install Docker Desktop. This follows the TRD literally, but the RAM cost is high on this machine.
2. **Native PostgreSQL + pgvector in an isolated conda env.** Chosen by the owner.
3. A remote PostgreSQL server. This would break the local-first goal.

## Decision

- Local dev: conda env `knowflow-pg` with `postgresql=17` and `pgvector`. The cluster lives in `data/postgres/`
  (gitignored) on `localhost:5432`, and `scripts/db.ps1` manages `install | init | start | stop | status`.
- `infra/docker-compose.yml` (image `pgvector/pgvector:pg17`) still ships for Docker hosts. CI uses the same
  image as a service container, so the Docker path stays exercised.
- Both paths run the same SQL in `infra/postgres/init/` (extension + roles), so the schema and roles are identical either way.

## Consequences

- The application code is identical in both modes. Only `DATABASE_URL` differs, and the default is the same.
- The Docker Compose path can't be run on the dev machine itself. It's verified in CI only, and the docs say so.
- PostgreSQL 17 satisfies the TRD's "16+" requirement.
