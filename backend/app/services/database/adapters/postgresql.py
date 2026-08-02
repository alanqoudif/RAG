from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.database.adapters.base import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    dialect = "postgresql"
    default_port = 5432
    driver_name = "postgresql+psycopg"

    def system_schemas(self) -> set[str]:
        return {"pg_catalog", "information_schema", "pg_toast"}

    def _connect_args(self, timeout_seconds: int) -> dict:
        return {"connect_timeout": timeout_seconds}

    def pre_execute_statements(self, timeout_seconds: int) -> list[str]:
        return [f"SET statement_timeout = {int(timeout_seconds * 1000)}"]

    def _estimate_row_count(self, engine: Engine, schema_name: str, table_name: str) -> int | None:
        # Catalog-based estimate (pg_class.reltuples) — never COUNT(*) on customer tables.
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT reltuples::bigint FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = :schema AND c.relname = :table"
                    ),
                    {"schema": schema_name, "table": table_name},
                ).scalar()
                return int(result) if result is not None and result >= 0 else None
        except Exception:
            return None
