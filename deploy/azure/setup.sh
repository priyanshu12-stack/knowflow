#!/usr/bin/env bash
# Installs (or updates) KnowFlow on an Ubuntu 24.04 Azure VM. Safe to re-run: it pulls the latest
# `main`, migrates, rebuilds the web app and restarts the services.
#
# Usage on the VM:  bash setup.sh <public-domain>
# Normally run for you by `deploy/azure/knowflow-azure.ps1 create` / `update`.
#
# Layout: PostgreSQL 16 + pgvector in Docker (infra/docker-compose.yml, loopback only), Ollama as
# a system service, API / worker / web as systemd units on 127.0.0.1, and Caddy on 80/443 with
# automatic HTTPS and a password gate. Only Caddy is reachable from the internet.
set -euo pipefail

DOMAIN=${1:?usage: setup.sh <public-domain>}
REPO=${KNOWFLOW_REPO:-https://github.com/priyanshu12-stack/knowflow.git}
APP=$HOME/knowflow
RUN_USER=$(id -un)
log() { printf '\n[knowflow-setup] %s\n' "$*"; }

log "system packages"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  git curl make zstd python3.12-venv docker.io docker-compose-v2 caddy
sudo systemctl enable --now docker

if ! command -v node >/dev/null || [[ "$(node -v)" != v22* ]]; then
  log "Node.js 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y -q nodejs
fi

if ! command -v ollama >/dev/null; then
  log "Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
fi
# Keep models in RAM for 30 minutes between questions (the default 5 minutes forces reloads).
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_KEEP_ALIVE=30m"\nEnvironment="OLLAMA_HOST=127.0.0.1:11434"\n' \
  | sudo tee /etc/systemd/system/ollama.service.d/knowflow.conf >/dev/null
sudo systemctl daemon-reload && sudo systemctl enable --now ollama && sudo systemctl restart ollama
for i in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done
log "model weights (first run downloads ~3.5 GB)"
ollama pull qwen3:4b
ollama pull nomic-embed-text:v1.5

log "application code"
if [[ -d "$APP/.git" ]]; then
  git -C "$APP" pull --ff-only
else
  git clone "$REPO" "$APP"
fi
cd "$APP"

if [[ ! -f .env ]]; then
  log "creating .env with random secrets"
  rand() { python3 -c 'import secrets; print(secrets.token_urlsafe(24))'; }
  cp .env.example .env
  sed -i \
    -e "s/^APP_ENV=.*/APP_ENV=production/" \
    -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(rand)/" \
    -e "s/^DEMO_DB_READER_PASSWORD=.*/DEMO_DB_READER_PASSWORD=$(rand)/" \
    .env
  chmod 600 .env
fi

log "PostgreSQL 16 + pgvector (Docker, loopback only)"
sudo docker compose -f infra/docker-compose.yml --env-file .env up -d --wait

log "Python and Node dependencies"
[[ -x apps/api/.venv/bin/python ]] || python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -q -c apps/api/requirements.lock -e apps/api
(cd apps/web && npm ci --no-audit --no-fund --loglevel=error)

log "database migrations and SQL demo"
(cd apps/api && .venv/bin/alembic upgrade head)
(cd apps/api && .venv/bin/python -m app.modules.sql_assistant.demo)

log "production web build"
(cd apps/web && NEXT_TELEMETRY_DISABLED=1 npm run build)

log "systemd services"
unit() { # unit <name> <description> <workdir> <command...>
  local name=$1 desc=$2 dir=$3; shift 3
  sudo tee "/etc/systemd/system/$name.service" >/dev/null <<EOF
[Unit]
Description=$desc
After=network-online.target docker.service ollama.service
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$dir
Environment=NEXT_TELEMETRY_DISABLED=1
ExecStart=$*
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}
unit knowflow-api "KnowFlow API" "$APP/apps/api" \
  "$APP/apps/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log"
unit knowflow-worker "KnowFlow ingestion worker" "$APP/apps/api" \
  "$APP/apps/api/.venv/bin/python -m app.workers.ingestion"
unit knowflow-web "KnowFlow web" "$APP/apps/web" \
  "$APP/apps/web/node_modules/.bin/next start -H 127.0.0.1 -p 3000"
sudo systemctl daemon-reload
sudo systemctl enable knowflow-api knowflow-worker knowflow-web >/dev/null
sudo systemctl restart knowflow-api knowflow-worker knowflow-web

log "Caddy (HTTPS + password gate)"
AUTH=/etc/caddy/knowflow-auth.caddy
if [[ ! -f "$AUTH" ]]; then
  # Locked until the owner sets a password (knowflow-azure.ps1 set-password): a random,
  # never-shown password means nobody can get in yet.
  locked=$(caddy hash-password --plaintext "$(python3 -c 'import secrets; print(secrets.token_hex(32))')")
  printf 'basicauth {\n\tadmin %s\n}\n' "$locked" | sudo tee "$AUTH" >/dev/null
fi
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$DOMAIN {
	import $AUTH
	request_body {
		max_size 30MB
	}
	reverse_proxy 127.0.0.1:3000 {
		transport http {
			read_timeout 10m
		}
	}
}
EOF
sudo systemctl enable caddy >/dev/null
sudo systemctl restart caddy

log "waiting for the API"
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8000/api/v1/health/live >/dev/null && break; sleep 2; done
curl -sf -X POST http://127.0.0.1:8000/api/v1/evaluations/sample >/dev/null \
  && log "sample documents queued for indexing (existing ones are kept)" \
  || log "WARNING: could not load the sample documents; check: journalctl -u knowflow-api"

log "done: https://$DOMAIN"
