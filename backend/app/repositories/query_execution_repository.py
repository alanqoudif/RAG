import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.query_execution import QueryExecution


def create(db: Session, execution: QueryExecution) -> QueryExecution:
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def get_by_id(db: Session, tenant_id: uuid.UUID, execution_id: uuid.UUID) -> QueryExecution | None:
    return db.execute(
        select(QueryExecution).where(
            QueryExecution.id == execution_id, QueryExecution.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def list_by_message_id(db: Session, tenant_id: uuid.UUID, message_id: uuid.UUID) -> list[QueryExecution]:
    return list(
        db.execute(
            select(QueryExecution).where(
                QueryExecution.tenant_id == tenant_id, QueryExecution.message_id == message_id
            )
        ).scalars()
    )
