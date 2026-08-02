"""The generic database agent: one code path for every tenant/connection/table combination.

Per the assignment's agent design rule, there is no per-table or per-tenant special-casing here —
this function is handed a request-specific, permission-filtered schema and behaves identically
regardless of which industry or tenant it is serving.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.constants import (
    AUDIT_SQL_EXECUTED,
    AUDIT_SQL_GENERATED,
    AUDIT_SQL_REJECTED,
    EXECUTION_FAILED,
    EXECUTION_SUCCESS,
    VALIDATION_FAILED,
    VALIDATION_PASSED,
)
from app.core.tenant_context import CurrentUser
from app.models.database_connection import DatabaseConnection
from app.models.query_execution import QueryExecution
from app.repositories import query_execution_repository
from app.services.audit_service import record_audit_event
from app.services.database import permission_service, query_executor
from app.services.database.connection_service import to_connection_details
from app.services.database.dialect_resolver import get_adapter
from app.services.database.query_executor import ExecutionResult
from app.services.database.query_validator import validate_and_secure
from app.services.database.sql_generator import generate_sql
from app.services.llm.ollama_client import OllamaClient


class TextToSqlOutcome:
    def __init__(
        self,
        *,
        query_execution: QueryExecution,
        execution_result: ExecutionResult | None,
        answer_note: str | None = None,
    ):
        self.query_execution = query_execution
        self.execution_result = execution_result
        self.answer_note = answer_note


async def ask_database(
    db: Session,
    *,
    connection: DatabaseConnection,
    question: str,
    current_user: CurrentUser,
    ollama_client: OllamaClient,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> TextToSqlOutcome:
    settings = ollama_client.settings

    allowed_tables = permission_service.resolve_allowed_tables(
        db, connection_id=connection.id, current_user=current_user
    )
    prompt_schema = permission_service.to_prompt_schema(allowed_tables)

    if not prompt_schema:
        execution = _save_execution(
            db,
            connection=connection,
            current_user=current_user,
            conversation_id=conversation_id,
            message_id=message_id,
            question=question,
            generated_sql="",
            validation_status=VALIDATION_FAILED,
            validation_errors=["No tables are permitted for this user on this connection."],
        )
        return TextToSqlOutcome(
            query_execution=execution,
            execution_result=None,
            answer_note="You do not have access to any tables on this database connection.",
        )

    candidate_sql = await generate_sql(
        ollama_client, question=question, allowed_schema=prompt_schema, dialect=connection.database_type
    )
    record_audit_event(
        db,
        action=AUDIT_SQL_GENERATED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=ip_address,
        request_id=request_id,
        details={"has_candidate": candidate_sql is not None},
    )

    if candidate_sql is None:
        execution = _save_execution(
            db,
            connection=connection,
            current_user=current_user,
            conversation_id=conversation_id,
            message_id=message_id,
            question=question,
            generated_sql="",
            validation_status=VALIDATION_FAILED,
            validation_errors=["The model determined the question cannot be answered from the allowed schema."],
        )
        return TextToSqlOutcome(
            query_execution=execution,
            execution_result=None,
            answer_note="This question cannot be answered using the connected database schema.",
        )

    validation = validate_and_secure(
        candidate_sql, database_type=connection.database_type, allowed_tables=allowed_tables, settings=settings
    )

    if not validation.ok:
        record_audit_event(
            db,
            action=AUDIT_SQL_REJECTED,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            resource_type="database_connection",
            resource_id=connection.id,
            ip_address=ip_address,
            request_id=request_id,
            details={"errors": validation.errors},
        )
        execution = _save_execution(
            db,
            connection=connection,
            current_user=current_user,
            conversation_id=conversation_id,
            message_id=message_id,
            question=question,
            generated_sql=candidate_sql,
            validation_status=VALIDATION_FAILED,
            validation_errors=validation.errors,
        )
        return TextToSqlOutcome(
            query_execution=execution,
            execution_result=None,
            answer_note="The generated query could not be validated as safe and was not executed.",
        )

    assert validation.query is not None  # guaranteed by validation.ok above
    validated = validation.query
    adapter = get_adapter(connection.database_type)
    details = to_connection_details(connection)
    result = query_executor.execute_query(
        adapter, details, validated.normalized_sql, allowed_tables=allowed_tables, settings=settings
    )

    record_audit_event(
        db,
        action=AUDIT_SQL_EXECUTED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=ip_address,
        request_id=request_id,
        details={"ok": result.ok, "row_count": result.row_count, "referenced_tables": validated.referenced_tables},
    )

    execution = _save_execution(
        db,
        connection=connection,
        current_user=current_user,
        conversation_id=conversation_id,
        message_id=message_id,
        question=question,
        generated_sql=candidate_sql,
        normalized_sql=validated.normalized_sql,
        query_type=validated.query_type,
        validation_status=VALIDATION_PASSED,
        validation_errors=[],
        applied_row_filters=validated.applied_row_filters,
        referenced_tables=validated.referenced_tables,
        referenced_columns=validated.referenced_columns,
        execution_status=EXECUTION_SUCCESS if result.ok else EXECUTION_FAILED,
        execution_time_ms=result.execution_time_ms,
        returned_row_count=result.row_count,
        result_preview={"columns": result.columns, "rows": result.rows[:20]} if result.ok else None,
        error_code=result.error_code,
        error_message=result.error_message,
    )
    return TextToSqlOutcome(query_execution=execution, execution_result=result)


def _save_execution(
    db: Session,
    *,
    connection: DatabaseConnection,
    current_user: CurrentUser,
    conversation_id: uuid.UUID | None,
    message_id: uuid.UUID | None,
    question: str,
    generated_sql: str,
    validation_status: str,
    validation_errors: list[str],
    normalized_sql: str | None = None,
    query_type: str | None = None,
    applied_row_filters: dict | None = None,
    referenced_tables: list[str] | None = None,
    referenced_columns: list[str] | None = None,
    execution_status: str | None = None,
    execution_time_ms: int | None = None,
    returned_row_count: int | None = None,
    result_preview: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> QueryExecution:
    execution = QueryExecution(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        connection_id=connection.id,
        user_id=current_user.id,
        question=question,
        generated_sql=generated_sql or "",
        normalized_sql=normalized_sql,
        query_type=query_type,
        validation_status=validation_status,
        validation_errors=validation_errors,
        applied_row_filters=applied_row_filters or {},
        referenced_tables=referenced_tables or [],
        referenced_columns=referenced_columns or [],
        execution_status=execution_status,
        execution_time_ms=execution_time_ms,
        returned_row_count=returned_row_count,
        result_preview=result_preview,
        error_code=error_code,
        error_message=error_message,
    )
    return query_execution_repository.create(db, execution)
