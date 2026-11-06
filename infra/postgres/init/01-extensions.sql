-- Shared by Docker (docker-entrypoint-initdb.d) and native setup (scripts/db.ps1 init).
-- Runs once against POSTGRES_DB as the bootstrap superuser.
CREATE EXTENSION IF NOT EXISTS vector;
