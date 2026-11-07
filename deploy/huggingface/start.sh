#!/usr/bin/env bash
# Boots KnowFlow inside the Hugging Face Space container (see deploy/huggingface/Dockerfile).
#
# The free Space disk is ephemeral: every restart begins with an empty database, so this script
# initialises PostgreSQL, migrates, seeds the SQL demo and reloads the bundled sample documents
# each time. If PGDATA points at persistent storage, an existing cluster is reused instead.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$APP_DIR/apps/api"
WEB_DIR="$APP_DIR/apps/web"
PY="$API_DIR/.venv/bin"
PG_BIN=/usr/lib/postgresql/16/bin
PG_SOCKET=/tmp/knowflow-pgsock
LOG_DIR=/tmp/knowflow-logs
PORT="${PORT:-7860}"

log() { printf '[knowflow] %s\n' "$*"; }
rand() { "$PY/python" -c 'import secrets; print(secrets.token_urlsafe(24))'; }

wait_for() { # wait_for <name> <url> <seconds>: any HTTP answer (even 401/404) counts as up
  local name=$1 url=$2 limit=$3 i
  for ((i = 0; i < limit; i++)); do
    if [[ "$(curl -s -o /dev/null -w '%{http_code}' "$url")" != "000" ]]; then
      log "$name is up"; return 0
    fi
    sleep 1
  done
  log "ERROR: $name did not start within ${limit}s"; return 1
}

mkdir -p "$LOG_DIR" "$PG_SOCKET" "$APP_DIR/data"
chmod 700 "$PG_SOCKET"

# Internal-only secrets: nothing outside the container uses them, so random values per boot are
# fine. Set them as Space secrets only if PGDATA is on persistent storage.
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(rand)}"
export DEMO_DB_READER_PASSWORD="${DEMO_DB_READER_PASSWORD:-$(rand)}"

# --- PostgreSQL 16 + pgvector ---------------------------------------------------------------
if [[ ! -s "$PGDATA/PG_VERSION" ]]; then
  log "initialising PostgreSQL cluster in $PGDATA"
  pwfile=$(mktemp)
  printf '%s' "$POSTGRES_PASSWORD" >"$pwfile"
  # Local socket (a private 0700 dir) trusts the container user; TCP requires the password.
  "$PG_BIN/initdb" -D "$PGDATA" -U "$POSTGRES_USER" --pwfile="$pwfile" \
    --auth-local=trust --auth-host=scram-sha-256 -E UTF8 --locale=C >"$LOG_DIR/initdb.log"
  rm -f "$pwfile"
fi

"$PG_BIN/pg_ctl" -D "$PGDATA" -l "$LOG_DIR/postgres.log" -w \
  -o "-p $POSTGRES_PORT -c listen_addresses=127.0.0.1 -c unix_socket_directories=$PG_SOCKET" start

psql_admin() { "$PG_BIN/psql" -h "$PG_SOCKET" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -v ON_ERROR_STOP=1 "$@"; }

# Re-apply the password on every boot so a reused cluster matches this boot's environment.
psql_admin -d postgres -q -v role="$POSTGRES_USER" -v pw="$POSTGRES_PASSWORD" <<'SQL'
ALTER ROLE :"role" PASSWORD :'pw';
SQL
if [[ -z "$(psql_admin -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'")" ]]; then
  psql_admin -d postgres -q -c "CREATE DATABASE \"$POSTGRES_DB\""
fi
psql_admin -d "$POSTGRES_DB" -q -f "$APP_DIR/infra/postgres/init/01-extensions.sql"
log "PostgreSQL is up"

stop_all() {
  log "shutting down"
  kill $(jobs -p) 2>/dev/null || true
  "$PG_BIN/pg_ctl" -D "$PGDATA" -m fast stop >/dev/null 2>&1 || true
}
trap stop_all EXIT

# --- Ollama -----------------------------------------------------------------------------------
ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
OLLAMA_PID=$!
wait_for "Ollama" "http://127.0.0.1:11434/api/version" 60

# --- Database schema and SQL Analyst demo -----------------------------------------------------
(cd "$API_DIR" && "$PY/alembic" upgrade head)
(cd "$API_DIR" && "$PY/python" -m app.modules.sql_assistant.demo)

# --- API, worker, web -------------------------------------------------------------------------
(cd "$API_DIR" && exec "$PY/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --no-access-log --timeout-keep-alive 75) \
  >"$LOG_DIR/api.log" 2>&1 &
API_PID=$!
(cd "$API_DIR" && exec "$PY/python" -m app.workers.ingestion) >"$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!
(cd "$WEB_DIR" && exec ./node_modules/.bin/next start -H 127.0.0.1 -p 3000) >"$LOG_DIR/web.log" 2>&1 &
WEB_PID=$!

wait_for "API" "http://127.0.0.1:8000/api/v1/health/live" 120
wait_for "web" "http://127.0.0.1:3000/" 120

# Bundled sample documents + 50-question gold set (idempotent: existing documents are kept).
if [[ "${LOAD_SAMPLES:-true}" == "true" ]]; then
  curl -sf -X POST "http://127.0.0.1:8000/api/v1/evaluations/sample" >/dev/null \
    && log "sample documents queued for indexing" \
    || log "WARNING: could not load sample documents (see $LOG_DIR/api.log)"
fi

# Load the generation model into RAM now so the first question doesn't pay the load time.
curl -sf "http://127.0.0.1:11434/api/generate" \
  -d "{\"model\": \"$OLLAMA_GENERATION_MODEL\", \"keep_alive\": -1}" >/dev/null 2>&1 &

# --- Caddy: public port, optional password gate -----------------------------------------------
CADDYFILE=/tmp/Caddyfile
{
  printf '{\n\tadmin off\n\tauto_https off\n\tpersist_config off\n}\n\n'
  printf ':%s {\n' "$PORT"
  if [[ -n "${APP_PASSWORD:-}" ]]; then
    hash=$(caddy hash-password --plaintext "$APP_PASSWORD")
    printf '\tbasic_auth {\n\t\t%s %s\n\t}\n' "${APP_USERNAME:-admin}" "$hash"
  fi
  printf '\trequest_body {\n\t\tmax_size 30MB\n\t}\n'
  printf '\treverse_proxy 127.0.0.1:3000 {\n\t\ttransport http {\n\t\t\tread_timeout 10m\n\t\t}\n\t}\n'
  printf '}\n'
} >"$CADDYFILE"

if [[ -n "${APP_PASSWORD:-}" ]]; then
  log "password gate ON (user: ${APP_USERNAME:-admin})"
else
  log "WARNING: APP_PASSWORD is not set. Anyone who can open this Space can upload and delete data."
fi

caddy run --config "$CADDYFILE" --adapter caddyfile >"$LOG_DIR/caddy.log" 2>&1 &
CADDY_PID=$!
wait_for "Caddy" "http://127.0.0.1:$PORT/" 30
log "KnowFlow is ready on port $PORT"

# Stream the service logs to the Space's log panel.
tail -n +1 -F "$LOG_DIR/api.log" "$LOG_DIR/worker.log" "$LOG_DIR/web.log" "$LOG_DIR/caddy.log" &

# Supervise: if any service exits, stop everything so the Space restarts the container.
declare -A SERVICES=([ollama]=$OLLAMA_PID [api]=$API_PID [worker]=$WORKER_PID [web]=$WEB_PID [caddy]=$CADDY_PID)
while true; do
  for name in "${!SERVICES[@]}"; do
    if ! kill -0 "${SERVICES[$name]}" 2>/dev/null; then
      log "ERROR: $name stopped (log: $LOG_DIR/$name.log); exiting so the Space restarts"
      tail -n 40 "$LOG_DIR/$name.log" 2>/dev/null || true
      exit 1
    fi
  done
  sleep 5
done
