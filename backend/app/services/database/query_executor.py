"""Executes an already-validated, already-rewritten SQL string against the target connection.

This module never sees raw LLM output — only the normalized SQL produced by query_validator,
which has already had unauthorized objects rejected and mandatory filters/limits injected. It
adds the remaining runtime controls: a bounded read-only engine, a server-side statement timeout,
a result-size cap (bytes and rows), and column masking.
"""

import datetime
import decimal
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text

from app.config import Settings
from app.services.database.adapters.base import ConnectionDetails, DatabaseAdapter
from app.services.database.masking import mask_value
from app.services.database.permission_service import TableAccess


def _json_safe(value: object) -> object:
    """Query results can contain driver-native types (Decimal, date/datetime, UUID, bytes) that
    the platform DB's JSON column can't serialize directly — normalize them to JSON-safe types
    once here, rather than at every call site that might persist or return a result row.
    """
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class ExecutionResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None


def _column_mask_map(allowed_tables: dict[str, TableAccess]) -> dict[str, str]:
    mask_map: dict[str, str] = {}
    for access in allowed_tables.values():
        for column in access.columns.values():
            if column.mask_type and column.mask_type != "none":
                mask_map[column.name] = column.mask_type
    return mask_map


def execute_query(
    adapter: DatabaseAdapter,
    details: ConnectionDetails,
    normalized_sql: str,
    *,
    allowed_tables: dict[str, TableAccess],
    settings: Settings,
) -> ExecutionResult:
    url = adapter.build_url(details)
    engine = adapter.make_engine(url, timeout_seconds=settings.sql_max_execution_seconds)
    mask_map = _column_mask_map(allowed_tables)
    started = time.perf_counter()

    try:
        with engine.connect() as conn:
            for stmt in adapter.pre_execute_statements(settings.sql_max_execution_seconds):
                conn.execute(text(stmt))
            result = conn.execute(text(normalized_sql))
            columns = list(result.keys())

            rows: list[dict] = []
            truncated = False
            total_bytes = 0
            for raw_row in result:
                row_dict = {}
                for col, value in zip(columns, raw_row, strict=False):
                    row_dict[col] = _json_safe(mask_value(value, mask_map.get(col)))
                approx_size = sum(len(str(v)) for v in row_dict.values())
                if total_bytes + approx_size > settings.sql_max_result_bytes:
                    truncated = True
                    break
                total_bytes += approx_size
                rows.append(row_dict)
                if len(rows) >= settings.sql_max_rows:
                    break

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            ok=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_time_ms=elapsed_ms,
        )
    except Exception as exc:  # noqa: BLE001 -- any driver failure becomes a safe, generic result
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            ok=False,
            execution_time_ms=elapsed_ms,
            error_code=type(exc).__name__,
            error_message="The query could not be executed against the source database.",
        )
    finally:
        engine.dispose()
