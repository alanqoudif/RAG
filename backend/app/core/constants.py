"""Shared constants. Centralized to avoid magic strings/numbers scattered across services."""

# Built-in role names seeded per tenant. Additional custom roles may be created per tenant.
ROLE_TENANT_ADMIN = "tenant_admin"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

DEFAULT_ROLES = (ROLE_TENANT_ADMIN, ROLE_ANALYST, ROLE_VIEWER)

# User / connection / file status values
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
STATUS_COMPLETED = "completed"

# Supported live database connection types
DB_TYPE_POSTGRESQL = "postgresql"
DB_TYPE_MYSQL = "mysql"
DB_TYPE_SQLSERVER = "sqlserver"
SUPPORTED_DB_TYPES = (DB_TYPE_POSTGRESQL, DB_TYPE_MYSQL, DB_TYPE_SQLSERVER)

AUDIT_CONNECTION_CREATED = "connection_created"
AUDIT_CONNECTION_UPDATED = "connection_updated"
AUDIT_CONNECTION_DELETED = "connection_deleted"
AUDIT_CONNECTION_TESTED = "connection_tested"
AUDIT_SCHEMA_SYNCED = "schema_synchronized"
AUDIT_PERMISSION_CHANGED = "permission_changed"
AUDIT_SQL_GENERATED = "sql_generated"
AUDIT_SQL_REJECTED = "sql_rejected"
AUDIT_SQL_EXECUTED = "sql_executed"
AUDIT_SENSITIVE_DATA_MASKED = "sensitive_data_masked"

# Table/column access levels
ACCESS_READ = "read"
ACCESS_READ_WRITE = "read_write"

# Column masking strategies
MASK_NONE = "none"
MASK_FULL = "full"
MASK_PARTIAL = "partial"

# SQL query types allowed after validation
QUERY_TYPE_SELECT = "select"
QUERY_TYPE_WITH = "with"
QUERY_TYPE_EXPLAIN = "explain"

VALIDATION_PASSED = "passed"
VALIDATION_FAILED = "failed"

EXECUTION_SUCCESS = "success"
EXECUTION_FAILED = "failed"

# File processing statuses
STATUS_PROCESSING = "processing"

SUPPORTED_FILE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt"}
MAX_UPLOAD_FILE_SIZE_BYTES = 25 * 1024 * 1024

AUDIT_FILE_UPLOADED = "file_uploaded"
AUDIT_FILE_PROCESSED = "file_processed"
AUDIT_FILE_PROCESSING_FAILED = "file_processing_failed"

CITATION_TYPE_DOCUMENT = "document"
CITATION_TYPE_DATABASE = "database"

# Chat request intents
INTENT_GENERAL = "general"
INTENT_DATABASE = "database"
INTENT_DOCUMENT = "document"
INTENT_HYBRID = "hybrid"
INTENT_CLARIFICATION = "clarification"

AUDIT_CHAT_REQUEST = "chat_request"

MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"

# JWT
TOKEN_TYPE_ACCESS = "access"

# Audit actions (extended in later phases)
AUDIT_LOGIN_SUCCESS = "login_success"
AUDIT_LOGIN_FAILURE = "login_failure"
AUDIT_TOKEN_REFRESH = "token_refresh"
AUDIT_TOKEN_REFRESH_FAILURE = "token_refresh_failure"
AUDIT_LOGOUT = "logout"
