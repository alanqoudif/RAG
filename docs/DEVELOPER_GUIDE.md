# Developer Guide

## Local setup (without Docker, for fast iteration)

```bash
cd backend
uv venv --python 3.12 && source .venv/bin/activate   # or python3.12 -m venv .venv
uv pip install -e ".[dev]"                            # or pip install -e ".[dev]"

# Only the platform Postgres + whatever else a given test needs must be running for live tests;
# unit tests and most integration tests use an in-memory SQLite session (see tests/conftest.py)
# and need nothing running at all.
docker compose up -d postgres sample-business-db redis qdrant minio ollama

pytest -v
ruff check app tests scripts
mypy app
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to http://localhost:8000
```

## Project layout

```
backend/app/
├── main.py, config.py, dependencies.py, exceptions.py, logging_config.py
├── api/routes/            one file per resource, thin — validation + calling services
├── core/                  security, encryption, permissions (RBAC), constants, tenant_context
├── models/                SQLAlchemy ORM, one file per entity, registered in models/__init__.py
├── schemas/                Pydantic request/response models
├── repositories/          tenant-scoped data access — every function takes tenant_id explicitly
├── services/
│   ├── database/          adapters, connection/schema/permission services, SQL validator+executor
│   ├── documents/         parsers, chunking, embeddings, reranker, retrieval, citations
│   ├── chat/               intent classification, answer generation, chat orchestration entry point
│   └── llm/                Ollama client, prompt templates
├── agents/                 LangGraph state + graph + nodes (thin wrappers around services/)
├── storage/, vector_store/ MinIO and Qdrant wrappers
└── workers/                Celery app + tasks
```

**Rule of thumb**: routes call services, services call repositories, repositories touch models.
Agent nodes call services directly — the same functions the REST routes use — so there is exactly
one implementation of "ask the database a question" or "retrieve document evidence," used by both
the synchronous chat endpoint and the graph.

## Adding a migration

```bash
docker compose up -d postgres
cd backend
DATABASE_URL="postgresql+psycopg://platform:platform@localhost:5432/platform" \
  alembic revision --autogenerate -m "describe the change"
```

**Always regenerate against a database whose migration history is up to date** — autogenerate
diffs against the *current* database state, not the model definitions in isolation. If a debug
script or manual `Base.metadata.create_all()` ever touches the same database, the next
autogenerate will silently produce an incomplete migration. This happened once in this project
(see `IMPLEMENTATION_PLAN.md` §8); the fix was validating against a disposable, empty database.
When in doubt, spin up a throwaway container:

```bash
docker run -d --name migration-check -e POSTGRES_USER=platform -e POSTGRES_PASSWORD=platform \
  -e POSTGRES_DB=platform -p 5555:5432 pgvector/pgvector:pg16
DATABASE_URL="postgresql+psycopg://platform:platform@localhost:5555/platform" alembic upgrade head
# ... regenerate/verify here ...
docker rm -f migration-check
```

## Testing conventions

- `tests/unit/` — pure logic, no I/O, or uses the in-memory SQLite `db_session` fixture.
- `tests/integration/` — API-level (`TestClient`) or service-level, with external calls (Ollama,
  MinIO, Qdrant) mocked where the test's purpose is the orchestration/persistence logic, not the
  external system itself.
- `tests/security/` — cross-tenant isolation, SQL injection/destructive-SQL blocking, prompt
  injection.
- Files suffixed `_live.py` talk to real infrastructure (real Postgres on `:5433`, real Qdrant,
  real MinIO, real Ollama) and are **skipped automatically** (`pytest.mark.skipif`) when that
  infrastructure isn't reachable — this keeps the default `pytest` run hermetic while still
  proving the real integration works when you do bring the stack up.

```bash
docker compose up -d postgres sample-business-db qdrant minio ollama
pytest -v                          # live tests now run instead of skipping
pytest tests/unit tests/security   # fast subset, no infra needed
```

## Adding a new database dialect adapter

Subclass `app.services.database.adapters.base.DatabaseAdapter` and override:

- `driver_name`, `default_port` — class attributes
- `build_url()` — only if the dialect needs a non-standard URL shape (see `sqlserver.py`)
- `system_schemas()` — schemas to always exclude from discovery/validation
- `_connect_args()` — dialect-specific connect timeout kwarg
- `pre_execute_statements()` — optional server-side statement-timeout SQL
- `_estimate_row_count()` — optional catalog-based row estimate (never `COUNT(*)`)

Schema discovery itself (`discover_schemas`) is implemented once in the base class using
SQLAlchemy's `inspect()` API — you should not need to touch it. Register the new adapter in
`app.services.database.dialect_resolver._ADAPTERS`.

## Changing the LLM model

Never hardcode a model name. `OLLAMA_MODEL` / `OLLAMA_FALLBACK_MODEL` in `.env` control it; the
`OllamaClient` tries the primary model first and falls back automatically on any failure
(timeout, model not found, connection error).

## Code style

`ruff` (imports, common bugs) and `mypy` (type checking) both run clean against `app/` — treat any
new warning as something to fix before committing, not suppress. No comments explaining *what*
code does (names should do that); comments are reserved for non-obvious *why*.
