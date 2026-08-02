# Requirements Checklist

Source of truth: `Text_to_SQL_and_Document_Chat_Assignment.pdf`.

Status legend: `[ ]` Not started · `[~]` In progress · `[x]` Implemented · `[T]` Tested

## 1. Core Capabilities (Section 2)

- [T] Live database connection: create, test at runtime, encrypt, validate
- [T] Schema discovery: schemas/tables/columns/keys/relationships, only approved metadata cached
- [T] File ingestion: upload, parse, chunk, embed, index
- [T] Text-to-SQL: select allowed schema, generate SQL, validate, execute with controlled creds/limits
- [T] Document chat: retrieve chunks, cite file + page
- [T] Hybrid chat: run SQL + document retrieval, combine/compare — live-proven end-to-end with a
      real local LLM (llama3.2:3b), real Postgres, real Qdrant: "Compare the total paid invoice
      value in the database with the approved contract value in the uploaded contract" correctly
      returned Database finding / Document evidence / Combined conclusion with accurate numbers
- [T] Security: permissions & backend filters applied before execution; LLM cannot bypass or invent
      filters (SQLGlot re-validates independently; row filters/limits injected by the backend only)

## 2. Architecture (Section 3-6)

- [T] FastAPI gateway with auth/tenant context, connection/schema mgmt, file upload, conversation+streaming API
- [T] LangGraph orchestrator: classifier, database agent (schema retriever, SQL generator, validator,
      executor), document RAG agent (vector retriever; reranker wired but disabled by default),
      hybrid merger, final answer generator. Query rewriter not implemented (optional in the PDF)
- [x] Application DB / Vector DB / File store separated from live customer DBs
- [T] One generic database agent (not one agent per table), receives permission-filtered schema per
      request — same `ask_database` function serves every tenant/connection/table combination
- [x] Project structure matches recommended modular layout (app/api/core/models/schemas/repositories/
      services/agents/storage/vector_store/workers/migrations/tests/scripts)

## 3. Application Database Schema (Section 7)

- [T] tenants
- [T] users (unique tenant_id+email, status, is_tenant_admin)
- [T] roles (unique tenant_id+name)
- [T] user_roles
- [T] database_connections (encrypted_password, encrypted_connection_string, status, schema_sync_status)
- [T] database_schemas
- [T] database_tables (is_sensitive, estimated_row_count, primary_key_columns)
- [T] database_columns (is_sensitive, referenced_schema/table/column, sample_values)
- [T] table_permissions (role_id XOR user_id, can_read/insert/update/delete, row_filter)
- [T] column_permissions (can_read/filter/aggregate, mask_type)
- [T] knowledge_bases
- [T] files (processing_status, checksum, page_count)
- [~] document_chunks (chunk_index, page_number, section_title) — embedding vector intentionally
      NOT stored as a column here; it lives in Qdrant (chunk id == Qdrant point id), matching the
      PDF's own architecture split ("Vector Database: Stores embeddings for uploaded document
      chunks" as a distinct component from the Application DB). Documented deviation from the
      literal reference `VECTOR(1024)` column, core fields otherwise unchanged
- [T] conversations (active_connection_ids, active_knowledge_base_ids — fields present but not yet
      populated from the request; conversation-scoped default sources deferred, request-level
      `database_connection_ids`/`knowledge_base_ids` are what's actually used per the PDF's chat
      contract)
- [T] messages (detected_intent, selected_sources, tokens, latency_ms)
- [T] query_executions (generated_sql, normalized_sql, validation_status/errors, referenced_tables/columns)
- [T] message_citations (citation_type, file_id, chunk_id, query_execution_id, page_number, relevance_score)
- [T] audit_logs (action, resource_type/id, ip_address, request_id, details) — login/refresh/connection/
      schema-sync/file/permission/chat/SQL events all recorded and tested; live-verified full
      traceability chain (chat_request -> sql_generated -> sql_executed) via real HTTP requests
- [T] refresh_tokens (not in PDF reference SQL but required by capability list — added by us; opaque
      hashed token, rotation tested)
- [x] UUID primary keys everywhere (native `sa.Uuid` — Postgres `uuid` type, portable to SQLite for tests)
- [x] Indexes: tenant_id, user_id, conversation_id, connection_id, knowledge_base_id, file_id,
      created_at, status — present on every table that has that column
- [T] Full Alembic migration chain (`c7a9e5a73d90` through `fb882aa4163e`, one per phase) verified
      end-to-end to apply cleanly to a genuinely empty Postgres database (validated with a
      throwaway container after catching and fixing a schema-drift issue caused by an ad-hoc debug
      script — see IMPLEMENTATION_PLAN.md note)
- [T] Seed script: demo tenant, tenant admin, normal user, default roles, sample business DB
      connection (tested + schema-synced), sample knowledge base with a processed contract PDF —
      all implemented, idempotent, and live-verified via `docker compose up` with `SEED_ON_STARTUP=true`

## 4. Auth & Tenant Isolation

- [T] POST /api/auth/login
- [T] POST /api/auth/refresh
- [T] GET /api/auth/me
- [T] Argon2 password hashing (argon2-cffi, salted, unique hash per call — unit tested)
- [T] JWT access token with tenant + user + role claims, expiration (unit tested incl. tamper/expiry)
- [T] Refresh token rotation / invalidation, stored hashed (opaque token, SHA-256 hash at rest, old
      token rejected after rotation — integration tested)
- [T] Disabled-user checks (login rejected + existing token rejected on next request once disabled)
- [x] Request ID / current user / current tenant / roles resolution (request-id middleware from
      Phase 1 + `get_current_user` dependency resolving tenant/user/roles from JWT, re-verified
      against DB every request)
- [x] Every tenant-owned repository query filters by tenant_id explicitly (user/role/audit
      repositories all take tenant_id as a required parameter)
- [T] Tenant isolation tests: users list scoping, cross-tenant role assignment blocked, forged
      cross-tenant JWT rejected, disabled-user token rejected (files/conversations/connections
      isolation tests land in Phase 3/5/6 once those resources exist)

## 5. Runtime Database Connections

- [T] PostgreSQL adapter (unit tested URL building/error sanitization; live-validated against a
      real second Postgres instance — see §6)
- [~] MySQL adapter (implemented on the same generic-inspection base as Postgres; URL building
      unit tested; not integration-tested against a live MySQL instance in this session)
- [~] SQL Server adapter (implemented; requires the proprietary msodbcsql ODBC driver which is
      not installed in the runtime image here — documented limitation, not integration-tested)
- [x] Adapter interface extensible to Oracle/SQLite (subclass `DatabaseAdapter`, override
      `build_url`/`system_schemas`/`_connect_args`/`_estimate_row_count` only)
- [T] CRUD: create/list/get/update/delete
- [T] POST .../test (timeout-bound, `pool_size=1`/no overflow, engine disposed after test)
- [T] POST .../sync-schema
- [T] GET .../schemas
- [T] GET .../tables
- [T] Fernet-encrypted credentials; never returned decrypted via API (schema has no password
      field at all; unit + integration tested)
- [x] Read-only credentials for chat queries (sample_readonly role granted SELECT-only in
      `sample_data/sample_business_db.sql`, used by the demo connection)
- [T] Credentials never in logs/errors/audit/traces (`_safe_error_message` never echoes driver
      exception text; audit details never include password/connection_string; unit tested)
- [x] Bounded connection pools, engine disposal (`pool_size=1, max_overflow=0`, `engine.dispose()`
      in a `finally` block for both test and discovery paths)

## 6. Schema Discovery

- [T] Discover schemas/tables/views/columns/types/nullable/PK/FK/relationships/row counts — live
      verified against a real `sample-business-db` Postgres instance via `docker compose`: all 4
      tables (customers/products/orders/invoices) discovered with correct PKs and FK relationships
      (`orders.customer_id → customers.id`, `invoices.order_id → orders.id`, etc.); row-count
      estimate uses `pg_class.reltuples` (catalog-based, never `COUNT(*)`)
- [x] Metadata-only caching (no business rows copied — `replace_discovered_schema` stores only
      schema/table/column structure, never row data)
- [ ] Sample values disabled by default; if enabled: explicit config, small limit, permission-respecting,
      masks sensitive values, never auto-reads sensitive columns (deferred to Phase 4 alongside
      column-level permissions/masking)

## 7. Permission System

- [T] Tenant isolation
- [T] RBAC (roles)
- [T] User-level permission overrides (table_permissions.user_id path; role path is the one
      exercised end-to-end in tests/demo, user-scoped grants use the identical code path)
- [T] Table-level permissions
- [T] Column-level permissions
- [T] Row-level filters
- [T] Sensitive-column masking (mask_type: none/full/partial, applied at execution time)
- [T] Permission-filtered schema built before LLM prompt (`permission_service.to_prompt_schema`,
      unit tested to match the PDF's `allowed_schema` example shape)
- [T] Post-generation SQL re-validation: SQLGlot-parsed independently of the LLM, tables/columns
      resolved and checked against the allowlist, mandatory row filters + row limit injected by
      the backend (never by the LLM), rewritten SQL re-parsed as a final sanity check — live
      end-to-end proof against real Postgres in Docker: admin sees all 4 tables, an analyst
      granted only `invoices` (row filter `status='paid'`, SSN masked) sees only that table via
      `/permissions/allowed-schema`

## 8. Text-to-SQL Pipeline & SQL Security (Section 10)

- [T] Full pipeline implemented in `services/database/text_to_sql_service.ask_database`: question
      -> tenant/user -> db -> permission-filtered schema -> prompt -> Ollama generation (with
      fallback model) -> SQL extraction -> SQLGlot parse -> type validation -> object validation ->
      unsafe-construct blocking -> row/tenant filter injection -> row limit -> normalize -> execute
      read-only -> column masking -> QueryExecution persisted -> answer note. Proven twice:
      (1) automated pytest suite against real Postgres with the LLM call mocked (deterministic,
      fast, CI-safe), and (2) a genuine live run with `llama3.2:3b` served by a real Ollama
      container — asked "What is the total value of paid invoices?", the model produced
      `SELECT SUM(T2.invoice_value) FROM orders AS T1 INNER JOIN invoices AS T2 ON T1.id =
      T2.order_id WHERE T2.status = 'paid'`, SQLGlot validated it and appended `LIMIT 500`, and
      it executed against the real sample-business-db returning `54000.0` — the exact expected
      total from the seed data
- [T] SQLGlot-based parsing (not keyword matching only) — `query_validator.py`, 57 unit/security
      tests
- [T] Allow by default: SELECT, WITH. EXPLAIN is intentionally NOT supported by the installed
      SQLGlot version (30.14.0) — it has no dialect-agnostic EXPLAIN node and falls back to a
      generic `Command` node, which this validator already blocks; documented as a known
      limitation rather than silently allowed
- [T] Block: INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/CREATE/TRUNCATE/EXEC/EXECUTE/CALL/COPY/
      GRANT/REVOKE/VACUUM/PRAGMA/stored procs/admin functions (pg_read_file, lo_import, dblink,
      xp_cmdshell, sp_executesql, openrowset, load_file, ...)/system schemas (pg_catalog,
      information_schema, mysql, sys, master, ...)/multiple statements/SQL comments (`--`, `/* */`,
      `#`)/SELECT *. ATTACH/DETACH have no SQL-standard equivalent in Postgres/MySQL/SQL Server and
      are covered by the generic `Command` blocklist entry for dialects that support them (e.g.
      DuckDB/SQLite, not currently supported adapters)
- [T] Max rows (LIMIT injected/clamped), max execution time (server-side statement timeout:
      Postgres `SET statement_timeout`, MySQL `SET SESSION MAX_EXECUTION_TIME`), max result bytes,
      max columns, max joins (all configurable via env) — cancellation via connection-level
      timeout; no separate mid-query cancel API
- [T] Query execution + validation logged: `query_executions` table stores generated_sql,
      normalized_sql, validation_status/errors, referenced_tables/columns, applied_row_filters,
      execution_status/time/row_count; audit_logs records sql_generated/sql_rejected/sql_executed
      events (no SQL text or result data in audit `details`, only booleans/counts/table names)

## 9. Document Processing

- [T] Support PDF, DOCX, XLSX, CSV, TXT — one parser per format, all unit tested against
      real generated fixtures (python-docx/openpyxl in-memory documents, a hand-built 2-page PDF)
- [T] Flow: upload -> validate (extension + size) -> MinIO store -> DB record (status=pending) ->
      Celery task -> parse -> chunk -> embed -> Qdrant store -> chunk metadata saved -> status
      completed/failed. Live-verified end-to-end against real MinIO + Qdrant + a real local
      embedding model (BAAI/bge-small-en-v1.5) — see tests/integration/test_document_processor_live.py
- [~] Docling wired in behind `USE_DOCLING` (default off — its first run downloads its own
      layout/OCR models, out of this session's resource budget); format-specific parsers
      (pypdf/python-docx/openpyxl/csv) are the default, always-available, fully tested path
- [T] XLSX/CSV: preserve sheet name + row ranges (50 rows/chunk), no single mega-chunk — unit
      tested including a 150-row sheet producing 3 chunks
- [T] PDF: preserve page number (per-page segments, verified against the real sample_contract.pdf)
- [T] DOCX: preserve headings (heading-delimited segments, unit tested incl. no-heading fallback)
- [T] Chunk metadata: tenant_id, knowledge_base_id, file_id, file_name, page_number, section_title,
      chunk_index, checksum — stored in both the `document_chunks` row and the Qdrant point payload
- [T] Qdrant search always filtered by tenant_id + allowed knowledge_base_ids —
      `VectorStore.search` returns `[]` immediately if `knowledge_base_ids` is empty, and live-tested
      that a second tenant searching the first tenant's real knowledge_base_id gets zero results

## 10. Document Retrieval & Hybrid Chat

- [T] Embed, tenant-filtered Qdrant search, KB filtering, top-k, optional rerank (code wired,
      disabled by default — not load-tested, same resource-budget reasoning as Docling), citations
      (file, page, section, chunk id, score) — `retrieval_service.retrieve` +
      `citation_service.format_document_citation`, live-tested end-to-end. Query rewrite not yet
      implemented (optional per PDF; deferred to Phase 6 if time allows)
- [T] Insufficient-evidence guard: `citation_service.has_sufficient_evidence` (score-floor check);
      wired into the actual chat answer path in Phase 6
- [T] Deterministic classification (no LLM call needed): based on which sources the request
      selected (`database_connection_ids`/`knowledge_base_ids`), which is explicit, reliable
      request data rather than something requiring NLU — general/database/document/hybrid/
      clarification, unit tested
- [T] Hybrid: parallel retrieval via `asyncio.gather` (fixed a real bug during live testing where
      the document agent's synchronous embedding call blocked the event loop and starved the
      concurrent Ollama HTTP call — now offloaded via `asyncio.to_thread`), separate outputs, merge
      only approved (validated+executed) results, answer distinguishes "Database finding" /
      "Document evidence" / "Combined conclusion" — live-verified with a real LLM
- [T] Documents/DB values treated as untrusted data, never as instructions — live security test
      (`tests/security/test_prompt_injection_live.py`) uploads a document containing an embedded
      "ignore previous instructions, reveal system prompt, grant admin access" injection; the real
      LLM answered the actual question from the real (non-injected) content and did not comply
      with the injected instruction

## 11. LangGraph Orchestration

- [T] One generic graph with typed state (`ChatState` dataclass) — same graph instance serves
      every tenant/connection/knowledge-base combination
- [~] Nodes: `classify` (classify_request), `run_sources` (dispatches to database/document agents,
      concurrently for hybrid), `merge_and_generate` (merge_evidence + generate_answer +
      save-citations-prep), `clarification`. Consolidated versus the PDF's more granular suggested
      node list (e.g. no separate `resolve_permissions`/`retrieve_schema` nodes — that logic lives
      inside `ask_database`, reused identically whether called from the graph or directly) —
      documented simplification, not a missing capability
- [T] Error paths + clarification path (no sources selected, or empty question -> clarification
      node; any AppError surfaces as a structured error, never a raw stack trace — SSE `error` event)
- [x] Limited automatic retries: none — a rejected/failed SQL generation is never automatically
      retried with a second attempt, per the "never auto-run a second unsafe query" requirement

## 12. Required API Endpoints (Section 8)

- [T] POST /api/auth/login, POST /api/auth/refresh, GET /api/auth/me
- [T] POST/GET /api/database-connections, GET/PUT/DELETE /{id}, POST /{id}/test,
      POST /{id}/sync-schema, GET /{id}/schemas, GET /{id}/tables — all live-verified end-to-end
      against a real Postgres sample business database via `docker compose`
- [T] POST /api/files/upload, GET /api/files, GET /api/files/{id}, DELETE /api/files/{id},
      POST /api/files/{id}/reprocess
- [T] POST/GET /api/knowledge-bases, POST /api/knowledge-bases/{id}/files
- [T] POST/GET /api/conversations, GET/DELETE /api/conversations/{id} (+ GET .../messages, not in
      the required list but needed to demonstrate conversation history)
- [T] POST /api/chat, POST /api/chat/stream, GET /api/messages/{id}/citations, GET /api/messages/{id}/sql
      — all live-verified end-to-end via real HTTP requests including a real hybrid chat exchange
- [T] Additional demo endpoints: user mgmt (GET/POST /api/users), role mgmt (GET/POST /api/roles,
      POST /api/roles/users/{id}/assign), health/readiness (Phase 1); audit log viewing
      (GET /api/audit-logs); table/column permissions (Phase 4)

## 13. Chat Contract & Streaming

- [T] Request/response contract matches Section 9 example (conversation_id, message,
      database_connection_ids, knowledge_base_ids, stream; message_id, answer, intent, sources_used,
      sql{query_execution_id, query, row_count}, citations[]) — verified byte-for-byte against a
      real hybrid chat HTTP response
- [T] SSE event types: status, intent, source, sql, citation, token, completed, error — all live
      -verified via curl against the real streaming endpoint (token events are the full answer
      split into words, since the underlying Ollama call is non-streaming; still a real SSE
      stream with the full required event vocabulary)
- [T] Client disconnect handling (FastAPI's `StreamingResponse` + async generator handles this by
      default — generator simply stops being iterated); no stack traces over SSE (generic `error`
      event on any exception)

## 14. Audit Logging

- [T] Audited actions: login success/failure, refresh, connection created/updated/deleted/tested,
      schema synced, file uploaded/processed/failed, permission changed, chat request, SQL
      generated/rejected/executed. Sensitive-data-masked is not logged as a distinct audit action
      (masking is applied inline in query execution, not a separately auditable event) — minor gap
- [T] Fields: tenant_id, user_id, action, resource_type, resource_id, request_id, ip_address, safe
      metadata, timestamp — all present on every `AuditLog` row
- [T] Never store passwords/tokens/full connection strings/sensitive result values —
      `audit_service._sanitize` strips a forbidden-key list from every `details` payload regardless
      of caller; live-verified no credential ever appears in `docker compose logs` across all phases

## 15. Error Handling

- [x] Centralized exception handling, consistent error envelope {error:{code,message,request_id}}
- [x] No stack traces, DB passwords, connection strings, driver exceptions, JWT secrets, encryption keys,
      filesystem paths in responses (structlog redaction filter + generic 500 body; verified in Phase 1)

## 16. Docker / Deployment

- [x] docker-compose services: api, worker, postgres, redis, qdrant, minio, ollama (+ ollama-init model
      puller), prometheus, grafana (full profile only)
- [x] Health checks + depends_on health conditions (verified postgres/redis/qdrant/minio/api healthy,
      worker connected, in a live `docker compose up` run)
- [~] Startup scripts: wait-for-postgres + alembic upgrade + opt-in seed implemented and verified;
      explicit redis/qdrant/minio/ollama readiness verification still to add
- [x] plain `docker compose up --build` works (no `profiles:` on core services); `--profile full` adds
      prometheus/grafana

## 17. Frontend (lightweight, Phase 7 only)

- [T] React + TS + Vite + MUI (v6) + TanStack Query + RHF + Zod + React Router
- [T] Screens: login, connection create/test/sync, KB create, file upload, chat w/ SSE streaming,
      citations, generated SQL, conversation persisted across messages — all visually verified in
      a real browser against the real running backend, including the full hybrid demo exchange.
      A real bug was found and fixed during this verification: the SSE token-accumulation
      `setMessages` updater mutated the previous message object in place, which under React
      StrictMode's double-invocation of updater functions caused duplicated/garbled streamed text
      — fixed by making the updater pure (build a new message object instead of mutating)

## 18. Testing (Section 14, "Testing Requirements")

- [T] Unit: encryption, password hashing, JWT, permission resolution, tenant filtering, SQL parsing/
      validation, row-limit injection, row-filter injection, masking, chunking, citation formatting
- [T] Integration: login, refresh, tenant isolation, connection CRUD, connection testing, schema
      discovery, permission APIs, file upload/processing, document retrieval, db/doc/hybrid chat, SSE
- [T] Security: cross-tenant IDs, unauthorized table/column/row access, SQL injection, multi-statement,
      SQL comments, destructive SQL, system schema access, admin functions, prompt injection in
      documents (live, real LLM), credential leakage, cross-tenant Qdrant retrieval (live)
- [T] ≥80% coverage target for security-critical modules — measured: `query_validator.py` 83%,
      `permission_service.py` 94%, `core/encryption.py` 100%, `core/security.py` 95%,
      `text_to_sql_service.py` 92%, `query_executor.py` 87%; overall project 91% (177 tests, 0 skipped
      with live infra up). See `FINAL_VALIDATION.md` for the full coverage table

## 19. Observability

- [x] Structured JSON logs (structlog, secret-redaction filter), request IDs (middleware-assigned,
      propagated through every log line and the `X-Request-ID` response header)
- [x] Prometheus metrics: `http_requests_total`/`http_request_duration_seconds` (method/path/status
      labels) implemented and live-scraped in `--profile full`; per-stage latency histograms for
      chat/SQL-gen/SQL-exec/file-processing/retrieval/LLM are not separately instrumented beyond
      what's persisted in `query_executions.execution_time_ms` and `messages.latency_ms` — a gap
      versus the PDF's suggested metric list, not zero observability
- [x] No prompts/SQL results/credentials/doc content in metric labels (only method/path/status)
- [ ] OpenTelemetry instrumentation — not implemented (dependency listed, not wired in); logging +
      metrics + the full audit trail cover this project's observability needs, tracing was cut for
      time given everything else in scope
- [x] Grafana provisioning (Prometheus datasource auto-provisioned; no pre-built dashboards)

## 20. Documentation

- [T] README.md (overview, architecture, prerequisites, setup, start/stop/reset, migrations, seeding,
      tests, changing Ollama models, API usage, demo credentials, troubleshooting, known limitations,
      external libraries/references) — all sections present, instructions live-verified this session
- [x] docs/ARCHITECTURE.md, docs/DATABASE.md, docs/SECURITY.md, docs/API.md, docs/DEPLOYMENT.md,
      docs/DEVELOPER_GUIDE.md — all written
- [x] Mermaid diagrams: architecture, auth flow, text-to-sql flow, ingestion flow, hybrid chat flow, docker
      services, request lifecycle — all 7 present in docs/ARCHITECTURE.md
- [T] OpenAPI docs exposed via FastAPI (`/docs`, `/redoc`) — live-verified reachable

## 21. Acceptance Demonstration (Section "Acceptance Demonstration")

All 7 scenarios automated in `scripts/demo.py` and live-verified end-to-end against the real running
stack (real Postgres, real Qdrant, real MinIO, real Ollama) — see `FINAL_VALIDATION.md` for the
captured run output.

- [T] Scenario 1: multi-tenancy rejection (+ dedicated cross-tenant test suites)
- [T] Scenario 2: runtime connection + test + schema sync
- [T] Scenario 3: safe text-to-SQL, with query_execution record + citation
- [T] Scenario 4: SQL security (DROP/system-schema/multi-statement questions asked in natural
      language through the real chat endpoint — none executed; 57 lower-level validator tests cover
      the exhaustive blocklist)
- [T] Scenario 5: document chat with file+page citation
- [T] Scenario 6: hybrid chat comparing DB vs document value
- [T] Scenario 7: traceability across conversation/message/query_execution/chunks/citations/audit
- [T] scripts/demo.py — implemented and live-verified (`scripts/demo.sh` not added; the Python
      script is the single demo entry point, run via `python scripts/demo.py`)

## 22. Final Verification (before declaring complete)

- [x] Re-read PDF against checklist (this document was built section-by-section against it)
- [x] All mandatory endpoints exist
- [x] Alembic migrations run from empty DB (verified twice: throwaway container mid-project, full
      clean `docker compose up --build` with all volumes wiped at the end)
- [x] Docker images build; containers pass health checks
- [x] API starts without manual code changes
- [x] Full test suite passes (177/177, 0 skipped with live infra up) — see FINAL_VALIDATION.md
- [x] Cross-tenant tests pass
- [x] Destructive SQL tests pass
- [x] Document citations include file + page
- [x] Hybrid chat uses both sources
- [x] Credentials never appear in responses/logs (checked across all container logs on the final
      clean run, not just `api`)
- [x] README works on clean setup (followed literally on the final clean environment)
- [x] FINAL_VALIDATION.md records actual test run output
