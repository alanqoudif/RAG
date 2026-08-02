from app.services.database.adapters.base import ConnectionDetails
from app.services.database.adapters.mysql import MySQLAdapter
from app.services.database.adapters.postgresql import PostgreSQLAdapter
from app.services.database.adapters.sqlserver import SQLServerAdapter
from app.services.database.dialect_resolver import get_adapter


def _details(**overrides):
    defaults = dict(
        host="dbhost",
        port=None,
        database_name="mydb",
        username="user",
        password="p@ss/word!",
        ssl_enabled=False,
        connection_options={},
    )
    defaults.update(overrides)
    return ConnectionDetails(**defaults)


def test_postgresql_build_url_uses_default_port_and_encodes_password():
    adapter = PostgreSQLAdapter()
    url = adapter.build_url(_details())
    assert url.startswith("postgresql+psycopg://user:")
    assert "5432" in url
    assert "mydb" in url
    assert "p@ss/word!" not in url  # must be percent-encoded, not raw


def test_mysql_build_url_defaults():
    adapter = MySQLAdapter()
    url = adapter.build_url(_details())
    assert url.startswith("mysql+pymysql://")
    assert "3306" in url


def test_sqlserver_build_url_includes_odbc_driver_param():
    adapter = SQLServerAdapter()
    url = adapter.build_url(_details())
    assert url.startswith("mssql+pyodbc://")
    assert "driver=" in url
    assert "1433" in url


def test_system_schemas_exclude_catalogs():
    pg = PostgreSQLAdapter()
    assert "pg_catalog" in pg.system_schemas()
    assert "information_schema" in pg.system_schemas()

    mysql = MySQLAdapter()
    assert "mysql" in mysql.system_schemas()

    mssql = SQLServerAdapter()
    assert "sys" in mssql.system_schemas()


def test_get_adapter_resolves_known_types():
    assert isinstance(get_adapter("postgresql"), PostgreSQLAdapter)
    assert isinstance(get_adapter("mysql"), MySQLAdapter)
    assert isinstance(get_adapter("sqlserver"), SQLServerAdapter)


def test_get_adapter_rejects_unknown_type():
    from app.exceptions import ValidationAppError

    try:
        get_adapter("oracle")
        raise AssertionError("expected ValidationAppError")
    except ValidationAppError:
        pass


def test_test_connection_failure_never_leaks_password_in_message():
    adapter = PostgreSQLAdapter()
    details = _details(host="host-that-does-not-resolve.invalid", port=59999)
    result = adapter.test_connection(details, timeout_seconds=1)
    assert result.ok is False
    assert "p@ss/word!" not in result.message
    assert "host-that-does-not-resolve" not in result.message
