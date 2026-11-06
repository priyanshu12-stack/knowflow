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

- Local dev: conda env `knowflow-pg` with `postgresql=16` and `pgvector=0.8.6`. The cluster lives in `data/postgres/`
  (gitignored) on `localhost:5432`, and `scripts/db.ps1` manages `install | init | start | stop | status`.
- `infra/docker-compose.yml` (image `pgvector/pgvector:pg16`) still ships for Docker hosts. CI runs the same
  image as its test-database service and applies the same init SQL.
- Both paths run the same SQL from `infra/postgres/init/` (currently the `vector` extension; the read-only SQL role is
  added at M6), so the database setup is identical either way.

## Consequences

- The application code is identical in both modes. Only the `POSTGRES_*` values in `.env` would differ, and the defaults match.
- `docker compose up` itself can't be run on the dev machine. CI checks the Compose file with `docker compose config`
  and runs the same image, but it doesn't run `compose up`. The README says so.
- PostgreSQL 16 satisfies the TRD's "16+" requirement.

## Amendment (2026-11-06, same day)

The first attempt used PostgreSQL 17. The conda solver rejected `postgresql=17` with every
current `pgvector` build because of a `libpq` conflict. The solvable pairing on conda-forge win-64 was
**PostgreSQL 16.15 + pgvector 0.8.6**, verified installed with `vector.dll` present. Docker and CI were moved
to `pgvector/pgvector:pg16` so all three environments run the same major version.
