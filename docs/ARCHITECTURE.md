# Architecture

## Overview

```mermaid
flowchart TD
    Client[Client / Frontend] --> API[FastAPI Gateway]
    API --> Auth[Auth & Tenant Context]
    API --> Conn[Connection & Schema Mgmt]
    API --> Files[File Upload & Processing]
    API --> Chat[Conversation & Streaming API]

    Chat --> Graph[LangGraph Orchestrator]
    Graph --> Classify[classify_request]
    Classify --> DBAgent[Database Agent]
    Classify --> DocAgent[Document RAG Agent]
    DBAgent --> Merge[merge_and_generate]
    DocAgent --> Merge
    Merge --> Answer[Final Answer]

    DBAgent -->|read-only, bounded pool| CustomerDB[(Live Customer DB)]
    DocAgent --> Qdrant[(Qdrant Vector Store)]
    Files --> MinIO[(MinIO Object Storage)]
    Files --> Worker[Celery Worker]
    Worker --> Qdrant
    Worker --> Postgres

    Auth --> Postgres[(Platform Postgres)]
    Conn --> Postgres
    Chat --> Postgres
```

The platform database (Postgres) stores identities, permissions, connection metadata, schema
cache, files, conversations, and audit records. **Customer business data never leaves the customer
database** — it is queried live, read-only, through a validated pipeline, and only small result
previews are cached in `query_executions.result_preview` for traceability.

## Text-to-SQL flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant Perm as permission_service
    participant LLM as Ollama
    participant Val as query_validator (SQLGlot)
    participant Exec as query_executor
    participant DB as Customer DB

    U->>API: POST /api/chat {question, database_connection_ids}
    API->>Perm: resolve_allowed_tables(user, connection)
    Perm-->>API: permission-filtered schema
    API->>LLM: generate SQL from filtered schema + question
    LLM-->>API: candidate SQL
    API->>Val: validate_and_secure(candidate_sql, allowed_tables)
    Val->>Val: parse, block DDL/DML/admin fns/system schemas/comments/multi-stmt
    Val->>Val: inject row filters + row limit (backend-only, LLM never sees this step)
    Val-->>API: normalized SQL or rejection
    API->>Exec: execute_query(normalized_sql) [read-only, bounded pool, timeout]
    Exec->>DB: SELECT ...
    DB-->>Exec: rows
    Exec-->>API: masked result rows
    API-->>U: answer + sql summary + citations
```

The LLM only ever sees a **permission-filtered schema** (table/column names it's allowed to use)
and never the raw SQL security rules — it cannot see, bypass, or alter the row-filter/limit
injection step, which happens entirely in `query_validator.py` after generation.

## Document ingestion flow

```mermaid
flowchart LR
    Upload[POST /api/files/upload] --> Validate[validate extension/size]
    Validate --> MinIO[(MinIO: store original)]
    Validate --> FileRow[(files row: status=pending)]
    FileRow --> Task[Celery: process_file_task]
    Task --> Parse[parse: pypdf/python-docx/openpyxl/csv]
    Parse --> Chunk[chunk_segments: page/heading/row-range aware]
    Chunk --> Embed[embedding_service: bge-small-en-v1.5]
    Embed --> Qdrant[(Qdrant: upsert vectors + payload)]
    Embed --> ChunkRows[(document_chunks rows)]
    ChunkRows --> Done[files row: status=completed]
```

## Hybrid chat flow

```mermaid
flowchart TD
    Start([classify_request]) -->|both sources selected| RunSources[run_sources node]
    RunSources -->|asyncio.gather| DBAgent[database agent: ask_database]
    RunSources -->|asyncio.gather| DocAgent[document agent: retrieve]
    DBAgent --> Merge[merge_and_generate]
    DocAgent --> Merge
    Merge --> Prompt["Ollama: Database finding / Document evidence / Combined conclusion"]
    Prompt --> Save[persist Message + MessageCitations + audit chat_request]
```

Database and document retrieval run **concurrently** (`asyncio.gather`) for hybrid requests. The
document agent's embedding call is offloaded via `asyncio.to_thread` so it never blocks the event
loop the concurrent Ollama HTTP call needs — a real bug found and fixed during live testing (see
`IMPLEMENTATION_PLAN.md` §8).

## Authentication flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant DB as Platform DB

    U->>API: POST /api/auth/login {tenant_code, email, password}
    API->>DB: lookup tenant + user (tenant-scoped)
    API->>API: verify_password (Argon2)
    API->>API: create_access_token (JWT: sub, tenant_id, roles, exp)
    API->>DB: issue_refresh_token (opaque, SHA-256 hashed, stored)
    API-->>U: {access_token, refresh_token}
    U->>API: subsequent requests: Authorization: Bearer <access_token>
    API->>API: decode_access_token + re-verify user is_active in DB
    U->>API: POST /api/auth/refresh {refresh_token}
    API->>DB: validate + rotate (old token revoked, new one issued)
    API-->>U: {new access_token, new refresh_token}
```

## Docker services

```mermaid
flowchart TB
    subgraph Core [docker compose up]
        api[api :8000]
        worker[worker]
        postgres[(postgres :5432)]
        redis[(redis :6379)]
        qdrant[(qdrant :6333)]
        minio[(minio :9000/9001)]
        ollama[ollama :11434]
        ollama_init[ollama-init: one-shot model pull]
        sample_db[(sample-business-db :5433)]
    end
    subgraph Full ["--profile full adds"]
        frontend[frontend :4173]
        prometheus[prometheus :9090]
        grafana[grafana :3000]
    end
    api --> postgres
    api --> redis
    api --> qdrant
    api --> minio
    api --> ollama
    worker --> postgres
    worker --> redis
    worker --> minio
    worker --> qdrant
    ollama_init --> ollama
    frontend --> api
    prometheus --> api
    grafana --> prometheus
```

## Request lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as request_context_middleware
    participant R as Route handler
    participant EH as Exception handlers

    C->>MW: HTTP request
    MW->>MW: assign/propagate X-Request-ID, bind to structlog context
    MW->>R: call_next()
    alt success
        R-->>MW: response
    else AppError raised
        R--xEH: AppError
        EH-->>MW: {error:{code,message,request_id}}
    else unhandled exception
        R--xMW: Exception
        MW-->>MW: log full exception server-side only
        MW-->>C: 500 {error:{code:"INTERNAL_ERROR",...}} — no stack trace
    end
    MW->>MW: record Prometheus http_requests_total / duration
    MW-->>C: response + X-Request-ID header
```

## Modular layout

`app/api` (routes) → `app/services` (business logic, the "real" code) → `app/repositories`
(tenant-scoped data access) → `app/models` (SQLAlchemy ORM) → Postgres/Qdrant/MinIO/Ollama.
`app/agents` holds the LangGraph orchestration layer, which calls the *same* service functions
the REST routes call directly (`text_to_sql_service.ask_database`,
`retrieval_service.retrieve`) — there is no duplicated business logic between the synchronous
API surface and the graph.
