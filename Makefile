# POSIX / CI developer commands. Windows: use scripts/dev.ps1 and scripts/db.ps1 (same targets).
API := apps/api
WEB := apps/web
PY  := $(API)/.venv/bin

.PHONY: setup db-up db-down migrate api web lint test check

setup:
	python3 -m venv $(API)/.venv
	$(PY)/pip install -e '$(API)[dev]'
	cd $(WEB) && npm ci
	test -f .env || cp .env.example .env

db-up:
	docker compose -f infra/docker-compose.yml --env-file .env up -d --wait

db-down:
	docker compose -f infra/docker-compose.yml --env-file .env down

migrate:
	cd $(API) && .venv/bin/alembic upgrade head

api:
	cd $(API) && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

web:
	cd $(WEB) && npm run dev

lint:
	cd $(API) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy
	cd $(WEB) && npm run lint && npm run format:check && npm run typecheck

test:
	cd $(API) && KNOWFLOW_RUN_INTEGRATION=1 .venv/bin/pytest
	cd $(WEB) && npm test

check: lint test
	cd $(WEB) && npm run build
