import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_connection import DatabaseConnection


def get_by_id(db: Session, tenant_id: uuid.UUID, connection_id: uuid.UUID) -> DatabaseConnection | None:
    return db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def get_by_name(db: Session, tenant_id: uuid.UUID, name: str) -> DatabaseConnection | None:
    return db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == tenant_id, DatabaseConnection.name == name
        )
    ).scalar_one_or_none()


def list_by_tenant(db: Session, tenant_id: uuid.UUID) -> list[DatabaseConnection]:
    return list(
        db.execute(
            select(DatabaseConnection).where(DatabaseConnection.tenant_id == tenant_id)
        ).scalars()
    )


def create(db: Session, connection: DatabaseConnection) -> DatabaseConnection:
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def update(db: Session, connection: DatabaseConnection) -> DatabaseConnection:
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def delete(db: Session, connection: DatabaseConnection) -> None:
    db.delete(connection)
    db.commit()


def record_test_result(
    db: Session, connection: DatabaseConnection, *, status: str, message: str, tested_at: datetime
) -> DatabaseConnection:
    connection.status = status
    connection.last_test_message = message
    connection.last_tested_at = tested_at
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection
