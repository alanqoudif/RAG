from app.core.constants import DB_TYPE_MYSQL, DB_TYPE_POSTGRESQL, DB_TYPE_SQLSERVER
from app.exceptions import ValidationAppError
from app.services.database.adapters.base import DatabaseAdapter
from app.services.database.adapters.mysql import MySQLAdapter
from app.services.database.adapters.postgresql import PostgreSQLAdapter
from app.services.database.adapters.sqlserver import SQLServerAdapter

_ADAPTERS: dict[str, type[DatabaseAdapter]] = {
    DB_TYPE_POSTGRESQL: PostgreSQLAdapter,
    DB_TYPE_MYSQL: MySQLAdapter,
    DB_TYPE_SQLSERVER: SQLServerAdapter,
}


def get_adapter(database_type: str) -> DatabaseAdapter:
    adapter_cls = _ADAPTERS.get(database_type)
    if adapter_cls is None:
        raise ValidationAppError(f"Unsupported database_type '{database_type}'.")
    return adapter_cls()
