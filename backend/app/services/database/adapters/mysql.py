from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.database.adapters.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):
    dialect = "mysql"
    default_port = 3306
    driver_name = "mysql+pymysql"

    def system_schemas(self) -> set[str]:
        return {"information_schema", "mysql", "performance_schema", "sys"}

    def _connect_args(self, timeout_seconds: int) -> dict:
        return {"connect_timeout": timeout_seconds}

    def pre_execute_statements(self, timeout_seconds: int) -> list[str]:
        return [f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_seconds * 1000)}"]

    def _estimate_row_count(self, engine: Engine, schema_name: str, table_name: str) -> int | None:
        # Catalog-based estimate (information_schema.TABLES.TABLE_ROWS) — never COUNT(*).
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT TABLE_ROWS FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table"
                    ),
                    {"schema": schema_name, "table": table_name},
                ).scalar()
                return int(result) if result is not None else None
        except Exception:
            return None
