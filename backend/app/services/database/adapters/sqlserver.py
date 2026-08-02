from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.database.adapters.base import ConnectionDetails, DatabaseAdapter

#: Requires the Microsoft ODBC Driver for SQL Server to be installed in the runtime image
#: (not bundled by default here — see docs/DEPLOYMENT.md). Not integration-tested against a live
#: SQL Server instance in this environment; the interface and URL construction follow the same
#: pattern validated end-to-end for PostgreSQL and MySQL.
ODBC_DRIVER_NAME = "ODBC Driver 18 for SQL Server"


class SQLServerAdapter(DatabaseAdapter):
    dialect = "sqlserver"
    default_port = 1433
    driver_name = "mssql+pyodbc"

    def build_url(self, details: ConnectionDetails) -> str:
        username = quote_plus(details.username) if details.username else ""
        password = quote_plus(details.password) if details.password else ""
        host = details.host or "localhost"
        port = details.port or self.default_port
        database = details.database_name or ""
        auth = f"{username}:{password}@" if username else ""
        driver_param = quote_plus(ODBC_DRIVER_NAME)
        trust_cert = "yes" if details.connection_options.get("trust_server_certificate", True) else "no"
        encrypt = "yes" if details.ssl_enabled else "no"
        return (
            f"{self.driver_name}://{auth}{host}:{port}/{database}"
            f"?driver={driver_param}&TrustServerCertificate={trust_cert}&Encrypt={encrypt}"
        )

    def system_schemas(self) -> set[str]:
        return {
            "sys",
            "INFORMATION_SCHEMA",
            "guest",
            "db_owner",
            "db_accessadmin",
            "db_securityadmin",
            "db_ddladmin",
            "db_backupoperator",
            "db_datareader",
            "db_datawriter",
            "db_denydatareader",
            "db_denydatawriter",
        }

    def _connect_args(self, timeout_seconds: int) -> dict:
        return {"timeout": timeout_seconds}

    def _estimate_row_count(self, engine: Engine, schema_name: str, table_name: str) -> int | None:
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT SUM(p.rows) FROM sys.partitions p "
                        "JOIN sys.tables t ON t.object_id = p.object_id "
                        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
                        "WHERE s.name = :schema AND t.name = :table AND p.index_id IN (0, 1)"
                    ),
                    {"schema": schema_name, "table": table_name},
                ).scalar()
                return int(result) if result is not None else None
        except Exception:
            return None
