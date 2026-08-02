# Multi-Tenant Text-to-SQL and Document Chat Platform

A local, self-hosted backend that lets authenticated, tenant-scoped users connect live business
databases at runtime, upload documents, and ask natural-language questions answered from SQL data,
document evidence, or both — with permission-aware SQL generation, citations, and full audit trails.

Built for the assignment in [`Text_to_SQL_and_Document_Chat_Assignment.pdf`](Text_to_SQL_and_Document_Chat_Assignment.pdf).
See [`REQUIREMENTS_CHECKLIST.md`](REQUIREMENTS_CHECKLIST.md) for line-by-line requirement tracking and
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for the architecture and phased build plan.

> **Status:** Phase 1 complete (infra, FastAPI skeleton, Postgres, Alembic, health/logging/error
> handling). This README grows with each phase; see the checklist for current coverage.

## Prerequisites

- Docker Desktop (or compatible engine) with Docker Compose v2
- ~8GB RAM free for Docker (more if you switch to the `full` profile / `qwen3:8b`)
- No cloud account and no paid API key are required — everything runs locally.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

This starts: `postgres` (platform DB), `sample-business-db` (a seeded Postgres instance used to
demonstrate runtime connections — see below), `redis`, `qdrant`, `minio`, `ollama` (+ a one-shot
`ollama-init` job that pulls the configured model), `api`, and `worker`. The API is available at
`http://localhost:8000`, interactive docs at `http://localhost:8000/docs`.

### Sample business database

`sample-business-db` seeds `customers`/`products`/`orders`/`invoices` tables (see
[`sample_data/sample_business_db.sql`](sample_data/sample_business_db.sql)) and a read-only role for
registering a runtime connection through the API:

```json
POST /api/database-connections
{
  "name": "sample-business",
  "database_type": "postgresql",
  "host": "sample-business-db",
  "port": 5432,
  "database_name": "sample_business",
  "username": "sample_readonly",
  "password": "sample_readonly_pw"
}
```

Then `POST /api/database-connections/{id}/test` and `POST /api/database-connections/{id}/sync-schema`
to discover its tables/columns. From the host machine (outside Docker), use `host: "localhost"` and
`port: 5433` instead.

### Table/column permissions

Tenant admins see every synced table by default. To scope a non-admin role or user down to
specific tables/columns/rows:

```json
POST /api/database-connections/{connection_id}/permissions
{
  "role_id": "<role-uuid>",
  "table_id": "<table-uuid>",
  "can_read": true,
  "row_filter": {"column": "status", "op": "=", "value": "paid"},
  "column_permissions": [
    {"column_id": "<ssn-column-uuid>", "can_read": true, "mask_type": "full"}
  ]
}
```

`GET /api/database-connections/{connection_id}/permissions/allowed-schema` returns exactly what
the caller's own permissions resolve to — the same shape the LLM prompt is built from, so it
doubles as a way to verify a grant took effect.

### Documents and knowledge bases

```bash
# create a knowledge base
curl -X POST http://localhost:8000/api/knowledge-bases -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "contracts"}'

# upload a file (PDF/DOCX/XLSX/CSV/TXT) — processing runs asynchronously via Celery
curl -X POST http://localhost:8000/api/files/upload -H "Authorization: Bearer $TOKEN" \
  -F "upload=@sample_data/sample_contract.pdf" -F "knowledge_base_id=<kb-uuid>"

# poll GET /api/files/{id} until processing_status is "completed"
```

`scripts/seed.py` (when `SEED_ON_STARTUP=true`) also creates a `contracts` knowledge base and
processes `sample_data/sample_contract.pdf` synchronously at startup, so the demo tenant has a
ready-to-query document without waiting on the Celery worker.

Use the **full** profile for a larger local LLM, the reranker, and monitoring:

```bash
docker compose --profile full up --build
```

Switch models by editing `.env` (`OLLAMA_MODEL`, `OLLAMA_FALLBACK_MODEL`) — never hardcoded in code.
Recommended: `llama3.2:3b` (dev, laptop-friendly) or `qwen3:8b` (full, needs more RAM).

## Stopping / resetting

```bash
docker compose down            # stop containers, keep data volumes
docker compose down -v         # stop and wipe all local data (Postgres, Qdrant, MinIO, Ollama models)
```

## Migrations

Migrations run automatically on `api` container startup (`alembic upgrade head`). To run manually:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "describe change"
```

## Seeding demo data

Set `SEED_ON_STARTUP=true` in `.env` before `docker compose up`, or run on demand:

```bash
docker compose exec api python scripts/seed.py
```

## Running tests

Locally (fastest, uses SQLite in-memory for unit/integration tests that don't need Postgres-specific
features):

```bash
cd backend
uv venv --python 3.12 && source .venv/bin/activate   # or: python3.12 -m venv .venv
uv pip install -e ".[dev]"                            # or: pip install -e ".[dev]"
pytest -v
ruff check app tests scripts
```

Or inside Docker:

```bash
docker compose run --rm api pytest -v
```

## API usage

OpenAPI docs: `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.
See [`docs/API.md`](docs/API.md) for endpoint reference and example requests (added in later phases).

## Demo credentials

Set `SEED_ON_STARTUP=true` (or run `scripts/seed.py` manually — see above) to create:

| Role | Tenant code | Email | Password |
|---|---|---|---|
| Tenant admin | `acme` | `admin@acme.io` | `DemoAdmin123!` |
| Analyst (non-admin) | `acme` | `analyst@acme.io` | `DemoUser123!` |

Login: `POST /api/auth/login` with `{"tenant_code": "acme", "email": "...", "password": "..."}`.
Development-only values — never used outside a local Docker environment.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for diagrams (added in later phases) and
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §2 for the high-level component/data-flow overview.

## External libraries and references

See `backend/pyproject.toml` for the full dependency list. Notable choices and why:

- **FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic** — the assignment's recommended stack; async-capable,
  strong typing, mature migration tooling.
- **SQLGlot** — SQL parsing/validation independent of keyword matching, per the assignment's mandatory
  SQL security controls.
- **LangGraph** — one generic orchestration graph (not one agent per table), per the assignment's agent
  design rule.
- **Ollama** — local LLM serving, no API key, model configurable via env vars.
- **sentence-transformers (`BAAI/bge-small-en-v1.5`, optional `bge-m3`)** — local embeddings behind a
  provider interface so the model can be swapped for better Arabic/multilingual support.
- **Qdrant** — vector store, chosen over pgvector-only to keep vector search isolated and independently
  scalable, with mandatory tenant + knowledge-base filtering on every query.
- **pypdf / python-docx / openpyxl** — lightweight, dependency-free format parsers used by default;
  **Docling** is wired in behind `USE_DOCLING=true` for higher-quality layout-aware parsing but is
  off by default (its first run downloads its own layout/OCR models).
- **structlog + prometheus-client + OpenTelemetry** — structured JSON logs, metrics, and tracing without
  a hosted APM.

## Troubleshooting

- **`api` container unhealthy / restarting**: check `docker compose logs api` — the entrypoint waits for
  Postgres and runs migrations before starting Uvicorn; a stuck wait usually means Postgres isn't
  healthy yet (`docker compose logs postgres`).
- **Ollama model pull is slow / stuck**: `ollama-init` runs once and can take a while on first pull
  depending on model size and network speed; watch `docker compose logs ollama-init`. It is not
  re-pulled on every restart (Ollama caches models in the `ollama_data` volume).
- **Out of memory running `full` profile**: switch back to `docker compose up` (dev profile defaults),
  which uses a much smaller model and disables the reranker.

## Known limitations

Tracked precisely in [`REQUIREMENTS_CHECKLIST.md`](REQUIREMENTS_CHECKLIST.md); summarized in
`FINAL_VALIDATION.md` once the full build is complete. Notably so far:

- The MySQL and SQL Server database adapters are implemented (same generic-inspection design as the
  PostgreSQL adapter, which is live-tested against a real Postgres instance) but have not been
  integration-tested against live MySQL/SQL Server instances in this environment. The SQL Server
  adapter additionally requires the proprietary Microsoft ODBC Driver for SQL Server, which is not
  installed in the provided `Dockerfile` (EULA-gated, not bundled by default).

## Individual work acknowledgement

Implemented against the assignment's reference architecture and schema (PDF §3-§12), using publicly
documented APIs/patterns for FastAPI, SQLAlchemy, Alembic, SQLGlot, LangGraph, Qdrant, MinIO, and
Ollama. No shared or copied implementation was used.
