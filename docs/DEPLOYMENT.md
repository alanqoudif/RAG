# Deployment (local Docker)

This project targets local, self-hosted deployment only — no cloud account, no paid API, per the
assignment's constraints. "Deployment" here means `docker compose`.

## Profiles

| Command | Includes | Use case |
|---|---|---|
| `docker compose up --build` | postgres, sample-business-db, redis, qdrant, minio, ollama (+ ollama-init), api, worker | Default — laptop-friendly |
| `docker compose --profile full up --build` | everything above + frontend, prometheus, grafana | Full demo with monitoring UI |

Model/reranker size is controlled by env vars, not by the profile flag — see below.

## Environment configuration

Copy `.env.example` to `.env` and adjust. Key variables for the dev vs. full hardware profile:

| Variable | Dev (default) | Full |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2:3b` | `qwen3:8b` |
| `OLLAMA_FALLBACK_MODEL` | `qwen3:4b` | `qwen3:4b` |
| `RERANKER_ENABLED` | `false` | `true` |
| `CELERY_CONCURRENCY` | `1` | `4` |

To switch to the full model: edit `.env`, then `docker compose up -d ollama-init` to trigger the
pull (idempotent — already-pulled models are not re-downloaded; verified in this project by
restarting the `ollama` container and confirming `ollama list` still showed the model from a
previous session).

## Startup sequence

The `api` container's entrypoint (`scripts/entrypoint.sh`):

1. `scripts/wait_for_deps.py` polls the platform Postgres until reachable.
2. `alembic upgrade head` — applies every pending migration.
3. If `SEED_ON_STARTUP=true`: `scripts/seed.py` — idempotent (existence-checked), creates the demo
   tenant/admin/analyst, the sample business DB connection (tested + schema-synced), and a
   knowledge base with the sample contract PDF processed synchronously.
4. `exec uvicorn app.main:app --host 0.0.0.0 --port 8000`

The `worker` container's entrypoint only waits for the DB (no migrations — avoids a race with the
`api` container's migration run) before starting Celery.

## Health checks

Every service in the compose file has a `healthcheck`; `api` and `worker` `depends_on` Postgres
and Redis with `condition: service_healthy`, so they won't start against a database that isn't
ready yet.

```bash
docker compose ps                     # STATUS column shows (healthy)/(unhealthy)
curl http://localhost:8000/api/health # liveness
curl http://localhost:8000/api/ready  # readiness (checks the platform DB)
```

## Resetting local state

```bash
docker compose down          # stop containers, keep volumes (including the pulled Ollama model)
docker compose down -v       # stop and wipe everything, including Ollama models — re-pull needed
```

## Monitoring (full profile)

- Prometheus (`:9090`) scrapes `api:8000/metrics` every 15s (`monitoring/prometheus/prometheus.yml`).
- Grafana (`:3000`, default admin/admin) is provisioned with the Prometheus datasource
  automatically (`monitoring/grafana/datasources/datasource.yml`); no pre-built dashboards ship —
  this was left out of scope for a college assignment, `/metrics` and the Prometheus UI are enough
  to demonstrate observability is wired up.

## Known limitation

MySQL and SQL Server database adapters are implemented but not integration-tested against live
instances in this repository — no MySQL/SQL Server container is included in the compose file. To
test them locally, add a `mysql:8` or
`mcr.microsoft.com/mssql/server:2022-latest` service and register a connection against it through
the API the same way the Postgres sample database is used; SQL Server additionally requires the
Microsoft ODBC Driver for SQL Server to be installed in the `backend/Dockerfile` (not bundled here
— proprietary, EULA-gated).
