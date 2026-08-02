import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.database_column import DatabaseColumn
from app.models.database_schema import DatabaseSchema
from app.models.database_table import DatabaseTable


def replace_discovered_schema(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    discovered_schemas: list,
) -> None:
    """Overwrite the cached metadata for this connection with a freshly discovered snapshot.

    Metadata-only: no business rows are copied here, only schema/table/column structure.
    """
    existing_schemas = db.execute(
        select(DatabaseSchema).where(DatabaseSchema.connection_id == connection_id)
    ).scalars()
    for schema in existing_schemas:
        db.delete(schema)
    db.flush()

    for schema_info in discovered_schemas:
        schema_row = DatabaseSchema(
            tenant_id=tenant_id, connection_id=connection_id, schema_name=schema_info.name
        )
        db.add(schema_row)
        db.flush()

        for table_info in schema_info.tables:
            table_row = DatabaseTable(
                tenant_id=tenant_id,
                connection_id=connection_id,
                schema_id=schema_row.id,
                table_name=table_info.name,
                table_type=table_info.table_type,
                estimated_row_count=table_info.estimated_row_count,
                primary_key_columns=table_info.primary_key_columns,
            )
            db.add(table_row)
            db.flush()

            for col in table_info.columns:
                db.add(
                    DatabaseColumn(
                        tenant_id=tenant_id,
                        table_id=table_row.id,
                        column_name=col.name,
                        data_type=col.data_type,
                        ordinal_position=col.ordinal_position,
                        is_nullable=col.is_nullable,
                        is_primary_key=col.is_primary_key,
                        is_foreign_key=col.is_foreign_key,
                        referenced_schema=col.referenced_schema,
                        referenced_table=col.referenced_table,
                        referenced_column=col.referenced_column,
                    )
                )
    db.commit()


def list_schemas(db: Session, tenant_id: uuid.UUID, connection_id: uuid.UUID) -> list[DatabaseSchema]:
    return list(
        db.execute(
            select(DatabaseSchema).where(
                DatabaseSchema.tenant_id == tenant_id, DatabaseSchema.connection_id == connection_id
            )
        ).scalars()
    )


def list_tables(
    db: Session, tenant_id: uuid.UUID, connection_id: uuid.UUID, *, schema_name: str | None = None
) -> list[DatabaseTable]:
    query = select(DatabaseTable).where(
        DatabaseTable.tenant_id == tenant_id, DatabaseTable.connection_id == connection_id
    )
    if schema_name is not None:
        query = query.join(DatabaseSchema).where(DatabaseSchema.schema_name == schema_name)
    return list(db.execute(query.options(selectinload(DatabaseTable.columns))).scalars())


def get_table_by_id(db: Session, tenant_id: uuid.UUID, table_id: uuid.UUID) -> DatabaseTable | None:
    return db.execute(
        select(DatabaseTable)
        .where(DatabaseTable.id == table_id, DatabaseTable.tenant_id == tenant_id)
        .options(selectinload(DatabaseTable.columns))
    ).scalar_one_or_none()
