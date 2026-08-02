"""Database adapter interface.

Each adapter knows how to build a driver-specific connection URL and expose it, but schema
discovery itself is implemented once here using SQLAlchemy's dialect-agnostic `inspect()` API —
avoids re-implementing information_schema queries per database. Subclasses override URL building,
the default port, system-schema exclusions, and connect-timeout wiring, which are the parts that
genuinely differ between PostgreSQL / MySQL / SQL Server. Oracle or SQLite can be added later by
subclassing `DatabaseAdapter` the same way, without touching the discovery logic.
"""

from abc import ABC
from dataclasses import dataclass, field

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.encryption import get_cipher


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_schema: str | None = None
    referenced_table: str | None = None
    referenced_column: str | None = None


@dataclass
class TableInfo:
    name: str
    table_type: str
    primary_key_columns: list[str] = field(default_factory=list)
    estimated_row_count: int | None = None
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class SchemaInfo:
    name: str
    tables: list[TableInfo] = field(default_factory=list)


@dataclass
class ConnectionTestResult:
    ok: bool
    message: str


class ConnectionDetails:
    """Everything needed to build a connection URL. Passwords are handled as plaintext here —
    this object only ever exists transiently in memory, decrypted just-in-time by the caller.
    """

    def __init__(
        self,
        *,
        host: str | None,
        port: int | None,
        database_name: str | None,
        username: str | None,
        password: str | None,
        ssl_enabled: bool = False,
        connection_options: dict | None = None,
    ):
        self.host = host
        self.port = port
        self.database_name = database_name
        self.username = username
        self.password = password
        self.ssl_enabled = ssl_enabled
        self.connection_options = connection_options or {}


class DatabaseAdapter(ABC):
    dialect: str
    default_port: int
    driver_name: str

    def build_url(self, details: ConnectionDetails) -> str:
        from urllib.parse import quote_plus

        username = quote_plus(details.username) if details.username else ""
        password = quote_plus(details.password) if details.password else ""
        host = details.host or "localhost"
        port = details.port or self.default_port
        database = details.database_name or ""
        auth = f"{username}:{password}@" if username else ""
        return f"{self.driver_name}://{auth}{host}:{port}/{database}"

    def system_schemas(self) -> set[str]:
        return set()

    def _connect_args(self, timeout_seconds: int) -> dict:
        return {}

    def pre_execute_statements(self, timeout_seconds: int) -> list[str]:
        """Statements run once per connection before a query, to cap server-side execution time
        as a second layer of defense on top of the client-side timeout/row limit.
        """
        return []

    def make_engine(self, url: str, *, timeout_seconds: int = 10) -> Engine:
        return create_engine(
            url,
            connect_args=self._connect_args(timeout_seconds),
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )

    def test_connection(self, details: ConnectionDetails, *, timeout_seconds: int = 5) -> ConnectionTestResult:
        url = self.build_url(details)
        engine = None
        try:
            engine = self.make_engine(url, timeout_seconds=timeout_seconds)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return ConnectionTestResult(True, "Connection successful.")
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any driver failure is a test failure
            return ConnectionTestResult(False, self._safe_error_message(exc))
        finally:
            if engine is not None:
                engine.dispose()

    def discover_schemas(self, details: ConnectionDetails, *, timeout_seconds: int = 20) -> list[SchemaInfo]:
        url = self.build_url(details)
        engine = self.make_engine(url, timeout_seconds=timeout_seconds)
        try:
            inspector = inspect(engine)
            schema_names = self._reflectable_schema_names(inspector, details)
            schemas: list[SchemaInfo] = []
            for schema_name in schema_names:
                tables = self._discover_tables(inspector, engine, schema_name)
                schemas.append(SchemaInfo(name=schema_name, tables=tables))
            return schemas
        finally:
            engine.dispose()

    def _reflectable_schema_names(self, inspector, details: ConnectionDetails) -> list[str]:
        try:
            all_schemas = inspector.get_schema_names()
        except Exception:
            all_schemas = [details.database_name or "public"]
        excluded = self.system_schemas()
        return [s for s in all_schemas if s not in excluded]

    def _discover_tables(self, inspector, engine: Engine, schema_name: str) -> list[TableInfo]:
        tables: list[TableInfo] = []
        try:
            table_names = inspector.get_table_names(schema=schema_name)
        except Exception:
            table_names = []
        try:
            view_names = inspector.get_view_names(schema=schema_name)
        except Exception:
            view_names = []

        for table_name, table_type in [(t, "table") for t in table_names] + [
            (v, "view") for v in view_names
        ]:
            tables.append(self._discover_one_table(inspector, engine, schema_name, table_name, table_type))
        return tables

    def _discover_one_table(
        self, inspector, engine: Engine, schema_name: str, table_name: str, table_type: str
    ) -> TableInfo:
        try:
            pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
            pk_columns = set(pk_constraint.get("constrained_columns") or [])
        except Exception:
            pk_columns = set()

        try:
            fks = inspector.get_foreign_keys(table_name, schema=schema_name)
        except Exception:
            fks = []
        fk_map: dict[str, tuple[str | None, str, str]] = {}
        for fk in fks:
            referred_schema = fk.get("referred_schema")
            referred_table = fk.get("referred_table")
            for local_col, remote_col in zip(
                fk.get("constrained_columns") or [], fk.get("referred_columns") or [], strict=False
            ):
                fk_map[local_col] = (referred_schema, referred_table, remote_col)

        columns: list[ColumnInfo] = []
        try:
            raw_columns = inspector.get_columns(table_name, schema=schema_name)
        except Exception:
            raw_columns = []

        for position, col in enumerate(raw_columns, start=1):
            name = col["name"]
            fk_target = fk_map.get(name)
            columns.append(
                ColumnInfo(
                    name=name,
                    data_type=str(col.get("type")),
                    ordinal_position=position,
                    is_nullable=bool(col.get("nullable", True)),
                    is_primary_key=name in pk_columns,
                    is_foreign_key=fk_target is not None,
                    referenced_schema=fk_target[0] if fk_target else None,
                    referenced_table=fk_target[1] if fk_target else None,
                    referenced_column=fk_target[2] if fk_target else None,
                )
            )

        row_count = self._estimate_row_count(engine, schema_name, table_name) if table_type == "table" else None

        return TableInfo(
            name=table_name,
            table_type=table_type,
            primary_key_columns=sorted(pk_columns),
            estimated_row_count=row_count,
            columns=columns,
        )

    def _estimate_row_count(self, engine: Engine, schema_name: str, table_name: str) -> int | None:
        """Best-effort, catalog-based estimate. Never runs COUNT(*) on customer tables."""
        return None

    def _safe_error_message(self, exc: Exception) -> str:
        """Return a short, generic message. Never echo the raw driver exception text back to the
        caller: it may embed the DSN (host/user/password) depending on the driver.
        """
        return f"{type(exc).__name__}: could not connect to the database within the configured timeout."


def decrypt_connection_password(encrypted_password: str | None) -> str | None:
    if not encrypted_password:
        return None
    return get_cipher().decrypt(encrypted_password)
