# KnowFlow on a free Hugging Face Docker Space (CPU basic: 2 vCPU, 16 GB RAM, no credit card).
#
# Everything runs in this one container: PostgreSQL 16 + pgvector, Ollama (qwen3:4b and
# nomic-embed-text:v1.5), the FastAPI API, the ingestion worker, Next.js and Caddy on port 7860.
# The Space repository holds only this file and README.md. The application code is cloned from
# GitHub during the build, so the Space never needs the repo's binary files (PNG/DOCX).
# Guide: docs/deploy-huggingface.md
#
# Still local-only inference (ADR-007): the models run inside this container, no API is called.

ARG KNOWFLOW_GITHUB=priyanshu12-stack/knowflow
ARG KNOWFLOW_REF=main

FROM caddy:2.10-alpine AS caddy
FROM node:22-bookworm-slim AS node

FROM ubuntu:24.04
ARG KNOWFLOW_GITHUB
ARG KNOWFLOW_REF
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# --- System packages: Python 3.12, PostgreSQL 16 + pgvector (PGDG repo, current pgvector).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg lsb-release zstd python3.12 python3.12-venv postgresql-common \
 && echo 'create_main_cluster = false' >> /etc/postgresql-common/createcluster.conf \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends postgresql-16 postgresql-16-pgvector \
 && rm -rf /var/lib/apt/lists/*

# --- Node 22 (for Next.js) and Caddy (password gate + reverse proxy), copied from official images.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

# --- Ollama. The Space has no GPU, so the bundled GPU libraries are removed to shrink the image.
RUN curl -fsSL https://ollama.com/install.sh | sh \
 && rm -rf /usr/local/lib/ollama/cuda_* /usr/local/lib/ollama/rocm* /usr/local/lib/ollama/vulkan*

# --- Hugging Face runs the container as uid 1000. Ubuntu 24.04 ships a uid-1000 "ubuntu" user.
RUN userdel -r ubuntu 2>/dev/null || true; useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=-1 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=2
WORKDIR /home/user

# --- Model weights (~3.5 GB). This layer comes before the code so code changes don't re-pull it.
RUN ollama serve >/tmp/ollama-build.log 2>&1 & \
    for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done; \
    ollama pull qwen3:4b && ollama pull nomic-embed-text:v1.5

# --- Application code. ADD of the branch ref busts the build cache whenever the branch moves,
#     so a "Factory rebuild" of the Space always picks up the latest pushed commit.
ADD --chown=user https://api.github.com/repos/${KNOWFLOW_GITHUB}/git/refs/heads/${KNOWFLOW_REF} /tmp/knowflow-ref.json
RUN git clone --depth 1 --branch "${KNOWFLOW_REF}" "https://github.com/${KNOWFLOW_GITHUB}.git" app
WORKDIR /home/user/app

# Editable install: the API locates the repo root (samples/, data/) from its source path.
RUN python3.12 -m venv apps/api/.venv \
 && apps/api/.venv/bin/pip install --no-cache-dir -c apps/api/requirements.lock -e apps/api

ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=http://127.0.0.1:8000
RUN cd apps/web && npm ci --no-audit --no-fund && npm run build

# --- Runtime configuration. Secrets (passwords, SECRET_KEY) are generated at boot unless set as
#     Space secrets; APP_PASSWORD (optional Space secret) turns on the password gate.
ENV APP_ENV=production \
    POSTGRES_HOST=127.0.0.1 \
    POSTGRES_PORT=5432 \
    POSTGRES_USER=knowflow \
    POSTGRES_DB=knowflow \
    PGDATA=/home/user/pgdata \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_GENERATION_MODEL=qwen3:4b \
    OLLAMA_EMBEDDING_MODEL=nomic-embed-text:v1.5 \
    GENERATION_TIMEOUT_SECONDS=540 \
    HEALTH_CHECK_TIMEOUT_SECONDS=5

EXPOSE 7860
CMD ["bash", "deploy/huggingface/start.sh"]
