export interface CurrentUser {
  id: string
  tenant_id: string
  email: string
  is_tenant_admin: boolean
  roles: string[]
}

export interface DatabaseConnection {
  id: string
  tenant_id: string
  name: string
  database_type: string
  host: string | null
  port: number | null
  database_name: string | null
  username: string | null
  ssl_enabled: boolean
  status: string
  last_tested_at: string | null
  last_test_message: string | null
  schema_sync_status: string
  last_schema_sync_at: string | null
  is_active: boolean
  created_at: string
}

export interface KnowledgeBase {
  id: string
  tenant_id: string
  name: string
  description: string | null
  created_at: string
}

export interface FileRecord {
  id: string
  tenant_id: string
  knowledge_base_id: string | null
  original_name: string
  mime_type: string | null
  extension: string | null
  file_size_bytes: number | null
  processing_status: string
  processing_error: string | null
  page_count: number | null
  extracted_text_length: number | null
  created_at: string
  processed_at: string | null
}

export interface Conversation {
  id: string
  tenant_id: string
  user_id: string
  title: string | null
  status: string
  created_at: string
  last_message_at: string | null
}

export interface ChatMessage {
  id: string
  conversation_id: string
  role: string
  content: string
  detected_intent: string | null
  selected_sources: unknown
  created_at: string
}

export interface Citation {
  type: string
  file_name?: string
  page?: number | null
  section?: string | null
  chunk_id?: string
  relevance_score?: number
  query_execution_id?: string
  tables?: string[]
}

export interface SqlSummary {
  query_execution_id: string
  query: string
  row_count: number
}

export interface ChatResponse {
  message_id: string
  conversation_id: string
  answer: string
  intent: string
  sources_used: string[]
  sql: SqlSummary | null
  citations: Citation[]
}
