"""Chat orchestration tests with the LLM and the database/document agents mocked at their
service boundary — this file verifies conversation/message/citation persistence, audit logging,
intent routing, and the API/SSE contract. The real end-to-end pipeline (real Ollama, real
Postgres, real Qdrant) is covered separately in tests/integration/test_hybrid_chat_live.py.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository
from app.services.database.query_executor import ExecutionResult
from app.services.documents.retrieval_service import RetrievedChunk


def _seed_admin_and_login(client, db_session, *, tenant_code="acme"):
    tenant = tenant_repository.create(db_session, name="Acme", code=tenant_code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    user = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email="admin@acme.io",
        password_hash=hash_password("Sup3rSecret!"),
        is_tenant_admin=True,
    )
    user_repository.assign_role(db_session, user_id=user.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    login = client.post(
        "/api/auth/login",
        json={"tenant_code": tenant_code, "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    return tenant, user, {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _mock_ollama(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.ollama_client.OllamaClient.generate",
        AsyncMock(return_value="This is a generated answer."),
    )


def test_chat_with_no_sources_returns_clarification(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    response = client.post("/api/chat", json={"message": "hello there"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "clarification"
    assert "conversation_id" in body
    assert "message_id" in body


def test_chat_database_intent_persists_query_execution_and_citation(client, db_session):
    tenant, admin, headers = _seed_admin_and_login(client, db_session)

    from app.models.database_connection import DatabaseConnection

    connection = DatabaseConnection(
        tenant_id=tenant.id, name="db", database_type="postgresql", host="h", port=5432
    )
    db_session.add(connection)
    db_session.commit()

    from app.repositories import query_execution_repository
    from app.services.database.text_to_sql_service import TextToSqlOutcome

    def _fake_ask_database(db, *, connection, question, current_user, ollama_client, **kwargs):
        from app.models.query_execution import QueryExecution

        execution = QueryExecution(
            tenant_id=current_user.tenant_id,
            connection_id=connection.id,
            user_id=current_user.id,
            question=question,
            generated_sql="SELECT SUM(invoice_value) AS total FROM invoices",
            normalized_sql="SELECT SUM(invoice_value) AS total FROM invoices LIMIT 500",
            query_type="select",
            validation_status="passed",
            referenced_tables=["invoices"],
            execution_status="success",
            returned_row_count=1,
        )
        query_execution_repository.create(db, execution)
        return TextToSqlOutcome(
            query_execution=execution,
            execution_result=ExecutionResult(
                ok=True, columns=["total"], rows=[{"total": 54000.0}], row_count=1
            ),
        )

    with patch(
        "app.agents.nodes.database_agent.text_to_sql_service.ask_database",
        new=AsyncMock(side_effect=_fake_ask_database),
    ):
        response = client.post(
            "/api/chat",
            json={"message": "total paid invoices?", "database_connection_ids": [str(connection.id)]},
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "database"
    assert "database" in body["sources_used"]
    assert body["sql"] is not None
    assert body["sql"]["row_count"] == 1
    assert len(body["citations"]) == 1
    assert body["citations"][0]["type"] == "database"

    sql_response = client.get(f"/api/messages/{body['message_id']}/sql", headers=headers)
    assert sql_response.status_code == 200
    assert len(sql_response.json()) == 1

    citations_response = client.get(f"/api/messages/{body['message_id']}/citations", headers=headers)
    assert citations_response.status_code == 200
    assert len(citations_response.json()) == 1


def test_chat_document_intent_persists_citation(client, db_session):
    tenant, admin, headers = _seed_admin_and_login(client, db_session)

    from app.models.knowledge_base import KnowledgeBase

    kb = KnowledgeBase(tenant_id=tenant.id, created_by=admin.id, name="contracts")
    db_session.add(kb)
    db_session.commit()

    fake_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        file_name="contract.pdf",
        content="Approved contract value is 60000 EGP.",
        page_number=2,
        section_title="Approved Contract Value",
        score=0.9,
    )

    with patch(
        "app.agents.nodes.document_agent.retrieve", return_value=[fake_chunk]
    ):
        response = client.post(
            "/api/chat",
            json={"message": "what is the contract value?", "knowledge_base_ids": [str(kb.id)]},
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "document"
    assert "documents" in body["sources_used"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["file_name"] == "contract.pdf"
    assert body["citations"][0]["page"] == 2


def test_chat_hybrid_intent_runs_both_sources(client, db_session):
    tenant, admin, headers = _seed_admin_and_login(client, db_session)

    from app.models.database_connection import DatabaseConnection
    from app.models.knowledge_base import KnowledgeBase

    connection = DatabaseConnection(
        tenant_id=tenant.id, name="db", database_type="postgresql", host="h", port=5432
    )
    kb = KnowledgeBase(tenant_id=tenant.id, created_by=admin.id, name="contracts")
    db_session.add_all([connection, kb])
    db_session.commit()

    from app.repositories import query_execution_repository
    from app.services.database.text_to_sql_service import TextToSqlOutcome

    def _fake_ask_database(db, *, connection, question, current_user, ollama_client, **kwargs):
        from app.models.query_execution import QueryExecution

        execution = QueryExecution(
            tenant_id=current_user.tenant_id,
            connection_id=connection.id,
            user_id=current_user.id,
            question=question,
            generated_sql="SELECT SUM(invoice_value) AS total FROM invoices",
            validation_status="passed",
            execution_status="success",
            returned_row_count=1,
        )
        query_execution_repository.create(db, execution)
        return TextToSqlOutcome(
            query_execution=execution,
            execution_result=ExecutionResult(ok=True, columns=["total"], rows=[{"total": 54000.0}], row_count=1),
        )

    fake_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        file_name="contract.pdf",
        content="Approved contract value is 60000 EGP.",
        page_number=2,
        section_title=None,
        score=0.9,
    )

    with (
        patch(
            "app.agents.nodes.database_agent.text_to_sql_service.ask_database",
            new=AsyncMock(side_effect=_fake_ask_database),
        ),
        patch("app.agents.nodes.document_agent.retrieve", return_value=[fake_chunk]),
    ):
        response = client.post(
            "/api/chat",
            json={
                "message": "compare invoices to contract value",
                "database_connection_ids": [str(connection.id)],
                "knowledge_base_ids": [str(kb.id)],
            },
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "hybrid"
    assert set(body["sources_used"]) == {"database", "documents"}
    assert len(body["citations"]) == 2


def test_chat_stream_emits_expected_event_types(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    with client.stream(
        "POST", "/api/chat/stream", json={"message": "hello"}, headers=headers
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: status" in body
    assert "event: intent" in body
    assert "event: token" in body or "event: completed" in body
    assert "event: completed" in body


def test_conversation_persists_across_messages(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    first = client.post("/api/chat", json={"message": "hello"}, headers=headers)
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/chat",
        json={"message": "hello again", "conversation_id": conversation_id},
        headers=headers,
    )
    assert second.json()["conversation_id"] == conversation_id

    messages_response = client.get(f"/api/conversations/{conversation_id}/messages", headers=headers)
    assert len(messages_response.json()) == 4  # 2 user + 2 assistant


def test_tenant_isolation_on_conversations(client, db_session):
    _, _, headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a")
    chat_response = client.post("/api/chat", json={"message": "hello"}, headers=headers_a)
    conversation_id = chat_response.json()["conversation_id"]

    _, _, headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b")
    response = client.get(f"/api/conversations/{conversation_id}", headers=headers_b)
    assert response.status_code == 404
