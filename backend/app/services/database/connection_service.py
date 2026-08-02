import uuid

from sqlalchemy.orm import Session

from app.core.encryption import get_cipher
from app.exceptions import ConflictError
from app.models.database_connection import DatabaseConnection
from app.repositories import database_connection_repository
from app.services.database.adapters.base import ConnectionDetails


def create_connection(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    name: str,
    database_type: str,
    host: str | None,
    port: int | None,
    database_name: str | None,
    username: str | None,
    password: str | None,
    ssl_enabled: bool,
    connection_options: dict,
) -> DatabaseConnection:
    if database_connection_repository.get_by_name(db, tenant_id, name) is not None:
        raise ConflictError("A connection with this name already exists in this tenant.")

    encrypted_password = get_cipher().encrypt(password) if password else None
    connection = DatabaseConnection(
        tenant_id=tenant_id,
        created_by=created_by,
        name=name,
        database_type=database_type,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
        encrypted_password=encrypted_password,
        ssl_enabled=ssl_enabled,
        connection_options=connection_options,
    )
    return database_connection_repository.create(db, connection)


def update_connection(
    db: Session,
    connection: DatabaseConnection,
    *,
    name: str | None = None,
    host: str | None = None,
    port: int | None = None,
    database_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
    ssl_enabled: bool | None = None,
    connection_options: dict | None = None,
) -> DatabaseConnection:
    if name is not None:
        connection.name = name
    if host is not None:
        connection.host = host
    if port is not None:
        connection.port = port
    if database_name is not None:
        connection.database_name = database_name
    if username is not None:
        connection.username = username
    if password is not None:
        connection.encrypted_password = get_cipher().encrypt(password)
    if ssl_enabled is not None:
        connection.ssl_enabled = ssl_enabled
    if connection_options is not None:
        connection.connection_options = connection_options
    return database_connection_repository.update(db, connection)


def to_connection_details(connection: DatabaseConnection) -> ConnectionDetails:
    password = get_cipher().decrypt(connection.encrypted_password) if connection.encrypted_password else None
    return ConnectionDetails(
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.username,
        password=password,
        ssl_enabled=connection.ssl_enabled,
        connection_options=connection.connection_options,
    )
