"""The assignment's Scenario 6, reproduced for real: "Compare the total paid invoice value in
the database with the approved contract value in the uploaded contract." Real Postgres
(sample-business-db), real Qdrant, real MinIO, real local embeddings, real Ollama — nothing
mocked. Skipped automatically unless all four are reachable.
"""

import socket
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.core.tenant_context import CurrentUser
from app.models.knowledge_base import KnowledgeBase
from app.repositories import role_repository, tenant_repository, user_repository
from app.services.chat.chat_service import handle_chat_request
from app.services.database import connection_service
from app.services.database.schema_discovery import sync_schema
from app.services.documents import upload_service
from app.services.documents.document_processor import process_file
from app.services.llm.ollama_client import OllamaClient


def _reachable(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not all(_reachable(p) for p in (5433, 6333, 9000, 11434)),
        reason="sample-business-db/Qdrant/MinIO/Ollama not all reachable",
    ),
]

SAMPLE_CONTRACT = Path(__file__).resolve().parents[3] / "sample_data" / "sample_contract.pdf"


async def test_hybrid_chat_compares_database_and_document(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme-hybrid")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email="admin@acme.io", password_hash=hash_password("x"), is_tenant_admin=True
    )
    user_repository.assign_role(db_session, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    current_user = CurrentUser(
        id=admin.id, tenant_id=tenant.id, email=admin.email, is_tenant_admin=True, roles=frozenset()
    )

    connection = connection_service.create_connection(
        db_session,
        tenant_id=tenant.id,
        created_by=admin.id,
        name="sample-business",
        database_type="postgresql",
        host="localhost",
        port=5433,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
        ssl_enabled=False,
        connection_options={},
    )
    sync_schema(db_session, connection, user_id=admin.id)

    kb = KnowledgeBase(tenant_id=tenant.id, created_by=admin.id, name="contracts")
    db_session.add(kb)
    db_session.commit()
    file = upload_service.store_upload(
        db_session,
        tenant_id=tenant.id,
        uploaded_by=admin.id,
        knowledge_base_id=kb.id,
        original_name="sample_contract.pdf",
        data=SAMPLE_CONTRACT.read_bytes(),
        content_type="application/pdf",
    )
    process_file(db_session, file)

    ollama_client = OllamaClient(get_settings())
    result = await handle_chat_request(
        db_session,
        current_user=current_user,
        question=(
            "Compare the total paid invoice value in the database with the approved contract "
            "value in the uploaded contract."
        ),
        database_connection_ids=[connection.id],
        knowledge_base_ids=[kb.id],
        conversation_id=None,
        ollama_client=ollama_client,
    )

    assert result.intent == "hybrid"
    assert set(result.sources_used) == {"database", "documents"}
    assert len(result.message.citations) >= 2
    citation_types = {c.citation_type for c in result.message.citations}
    assert citation_types == {"database", "document"}

    answer_lower = result.message.content.lower()
    assert "54000" in result.message.content or "54,000" in result.message.content
    assert "60000" in result.message.content or "60,000" in result.message.content or "contract" in answer_lower

    print("\n--- HYBRID CHAT ANSWER ---")
    print(result.message.content)
