# Implementation Plan

## 1. Scope and Strategy

This is a 4-day-scope college assignment (see PDF §13) reimplemented as a phased build. We follow the
phases defined in the working instructions (Phase 0-7), each ending with tests, lint, a Docker health
check, and a `REQUIREMENTS_CHECKLIST.md` update. No cloud accounts, no paid APIs — everything runs
locally via Docker Compose, using Ollama for the LLM and locally-hosted embedding/reranker models.

## 2. Local Architecture

```
Client (React demo / curl / Swagger UI)
        |
        v
FastAPI (uvicorn) ---- Prometheus /metrics, OpenTelemetry
        |
        +-- Auth & tenant context (JWT, Argon2, RBAC middleware)
        +-- Database connection & schema routes
        +-- File upload & knowledge base routes
        +-- Conversation & chat routes (JSON + SSE)
        |
        v
LangGraph orchestrator (agents/graph.py)
        |
        +-- classify_request -> resolve_permissions -> select_sources
        +-- Database agent: retrieve_schema -> generate_sql (Ollama) -> validate_sql (SQLGlot)
        |     -> execute_sql (read-only pooled engine per connection)
        +-- Document agent: retrieve_documents (Qdrant) -> rerank_documents (optional bge-reranker)
        +-- merge_evidence -> generate_answer (Ollama) -> save_results -> finalize
        |
        v
+---------------------------------------------------------+
| Postgres (platform DB + pgvector fallback not used;      |
| Qdrant is primary vector store) | Redis | MinIO | Qdrant |
+---------------------------------------------------------+
        |
        v
Live customer databases (Postgres / MySQL / SQL Server), read-only creds, bounded pools
```

Celery workers (backed by Redis) handle async file processing (parse -> chunk -> embed -> index) so
uploads return immediately and processing status is polled/streamed.

## 3. Directory Tree

```
RAG/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, dependencies.py, exceptions.py, logging_config.py
│   │   ├── api/router.py, api/routes/*.py
│   │   ├── core/ (security, encryption, permissions, constants, tenant_context)
│   │   ├── models/ (SQLAlchemy ORM models, one file per entity)
│   │   ├── schemas/ (Pydantic v2 request/response models)
│   │   ├── repositories/ (tenant-scoped data access)
│   │   ├── services/database|documents|chat|llm
│   │   ├── agents/graph.py, state.py, nodes/, prompts/
│   │   ├── infrastructure/ (db session, redis, minio, qdrant, ollama clients)
│   │   ├── storage/ (MinIO wrapper)
│   │   ├── vector_store/ (Qdrant wrapper)
│   │   └── workers/ (Celery app + tasks)
│   ├── migrations/ (Alembic)
│   ├── tests/{unit,integration,security}
│   ├── scripts/ (seed.py, demo.py, wait_for_deps.py)
│   ├── pyproject.toml, alembic.ini, Dockerfile
├── frontend/ (Vite React demo, built in Phase 7)
├── monitoring/{prometheus,grafana}
├── sample_data/ (sample contract PDF, sample business DB seed SQL)
├── docs/ (ARCHITECTURE, DATABASE, SECURITY, API, DEPLOYMENT, DEVELOPER_GUIDE)
├── docker-compose.yml, .env.example, README.md
├── REQUIREMENTS_CHECKLIST.md, IMPLEMENTATION_PLAN.md
```

## 4. Mandatory vs Optional

**Mandatory (graded acceptance criteria):** multi-tenancy isolation, runtime DB connections (Postgres +
at least one more dialect — we implement Postgres, MySQL, SQL Server per PDF), permission-filtered
schema + SQL, SQLGlot validation with the full blocklist, document ingestion (PDF/DOCX/XLSX/CSV/TXT),
citations, hybrid chat, traceability, audit logs, SSE streaming, Docker Compose, README, migrations,
tests (unit/integration/security).

**Optional / nice-to-have (build only if time remains after mandatory items are solid):** Prometheus +
Grafana dashboards beyond a minimal `/metrics` endpoint, OpenTelemetry tracing beyond basic
instrumentation, reranker model (explicitly optional per PDF stack), full React frontend polish, row-level
Postgres RLS (defense in depth — instructions call it "where practical"), Oracle/SQLite adapters (interface
must support them, implementation not required).

## 5. Local Hardware Profiles

| Profile | Ollama model | Embedding model | Reranker | Celery concurrency |
|---|---|---|---|---|
| `dev` (default) | `llama3.2:3b` (fallback `qwen3:4b`) | `BAAI/bge-small-en-v1.5` | disabled | 1 |
| `full` | `qwen3:8b` (fallback `qwen3:4b`) | `BAAI/bge-small-en-v1.5` (optionally `bge-m3`) | `BAAI/bge-reranker-base` enabled | 4 |

Rationale: this will primarily be developed and demoed on a laptop. `qwen3:8b` needs ~6-8GB RAM
free for Ollama alone; `llama3.2:3b` runs comfortably on 8GB total RAM machines and is fast enough for
iterative testing. Model name is always read from `OLLAMA_MODEL` / `OLLAMA_FALLBACK_MODEL` env
vars — never hardcoded. `bge-small-en-v1.5` (384-dim... actually 384 dim, but schema reference uses
VECTOR(1024) for bge-m3/bge-large-scale — we size the Qdrant collection from the configured
embedding model's actual dimension at startup, not a hardcoded constant).

Reranker is gated by `RERANKER_ENABLED=false` by default (it requires an extra ~1GB+ RAM for the
cross-encoder); the retrieval service works correctly with it disabled (skips the rerank step).

## 6. Commands

```bash
docker compose --profile dev up --build     # laptop-friendly
docker compose --profile full up --build    # qwen3:8b + reranker + full monitoring
docker compose up --build                   # equivalent to dev (default profile)
```

## 7. Phase Checklist (mirrors task tracker)

0. Requirements checklist, implementation plan, project skeleton — **this document**
1. Docker infra, FastAPI, config, Postgres, SQLAlchemy, Alembic, health, logging, error handling, tests
2. Tenants/users/roles, JWT auth, refresh tokens, Argon2, tenant middleware, RBAC, isolation tests
3. Runtime DB connections, encryption, adapters (Postgres/MySQL/SQL Server), schema discovery, cache
4. Table/column/row permissions, SQL generation (Ollama), SQLGlot validation, secure execution, limits
5. Knowledge bases, MinIO upload, parsing/chunking/embedding, Qdrant indexing, retrieval, citations
6. LangGraph orchestration, intent classification, hybrid chat, conversation persistence, audit, SSE
7. Lightweight frontend, final docs, full test suite, security validation, Docker validation, FINAL_VALIDATION.md

Each phase ends with: run tests → lint (ruff) → typecheck (mypy, best-effort) → docker health check →
update `REQUIREMENTS_CHECKLIST.md` → summary of files/features/tests → proceed automatically unless
genuinely blocked on a decision only the user can make.

## 8. Incident Log

**Phase 6 — schema drift from an ad-hoc debug script.** While debugging the hybrid-chat text-to-SQL
prompt, a one-off Python script called `Base.metadata.create_all(engine)` directly against the
shared dev Postgres container to quickly test model changes, bypassing Alembic. This created the
Phase 6 tables (conversations/messages/message_citations) in that database without an Alembic
migration recording them, so the next `alembic revision --autogenerate` only picked up the
leftover foreign-key additions and silently produced an incomplete migration (missing the
`CREATE TABLE` statements — it would have failed on any genuinely empty database). Caught by
routinely validating every migration against a **fresh, empty** database rather than trusting the
already-migrated dev instance. Fix: deleted the bad migration, stood up a disposable throwaway
Postgres container, replayed the full migration chain to confirm it matched the dev DB's
pre-drift state, regenerated the migration there (now correctly including all three `CREATE
TABLE`s), and reset the dev Postgres volume to pick up the corrected migration cleanly. Lesson
reinforced: debug/scratch scripts that touch a database should use a disposable database, not the
one whose migration history is being tracked.
