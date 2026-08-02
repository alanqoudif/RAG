"""End-to-end document pipeline against real MinIO + Qdrant + a real local embedding model
(no mocks). Requires `docker compose up -d minio qdrant`; skipped automatically otherwise.
Covers: upload -> MinIO storage -> parse (real sample_contract.pdf) -> chunk -> embed -> Qdrant
index -> retrieval -> tenant/knowledge-base-filtered search -> citation formatting.
"""

import socket
import uuid
from pathlib import Path

import pytest

from app.core.constants import ROLE_TENANT_ADMIN, STATUS_COMPLETED
from app.core.security import hash_password
from app.core.tenant_context import CurrentUser
from app.models.knowledge_base import KnowledgeBase
from app.repositories import role_repository, tenant_repository, user_repository
from app.services.documents import upload_service
from app.services.documents.citation_service import format_document_citation
from app.services.documents.document_processor import process_file
from app.services.documents.retrieval_service import retrieve


def _minio_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 9000), timeout=1):
            return True
    except OSError:
        return False


def _qdrant_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 6333), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not (_minio_reachable() and _qdrant_reachable()),
    reason="MinIO/Qdrant not reachable (run `docker compose up -d minio qdrant`)",
)

SAMPLE_CONTRACT = Path(__file__).resolve().parents[3] / "sample_data" / "sample_contract.pdf"


def _seed_tenant(db_session, code):
    tenant = tenant_repository.create(db_session, name=code, code=code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email=f"admin@{code}.io", password_hash=hash_password("x"), is_tenant_admin=True
    )
    user_repository.assign_role(db_session, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    return tenant, admin


def test_full_pipeline_upload_process_and_retrieve(db_session):
    tenant, admin = _seed_tenant(db_session, f"acme-{uuid.uuid4().hex[:8]}")
    kb = KnowledgeBase(tenant_id=tenant.id, created_by=admin.id, name="contracts")
    db_session.add(kb)
    db_session.commit()

    data = SAMPLE_CONTRACT.read_bytes()
    file = upload_service.store_upload(
        db_session,
        tenant_id=tenant.id,
        uploaded_by=admin.id,
        knowledge_base_id=kb.id,
        original_name="sample_contract.pdf",
        data=data,
        content_type="application/pdf",
    )

    process_file(db_session, file)
    db_session.refresh(file)

    assert file.processing_status == STATUS_COMPLETED
    assert file.page_count == 2
    assert file.extracted_text_length is not None and file.extracted_text_length > 0

    current_user = CurrentUser(
        id=admin.id, tenant_id=tenant.id, email=admin.email, is_tenant_admin=True, roles=frozenset()
    )
    results = retrieve(
        db_session,
        tenant_id=tenant.id,
        knowledge_base_ids=[kb.id],
        query="What is the approved contract value?",
    )
    assert len(results) > 0
    top = results[0]
    assert "60000" in top.content or "contract value" in top.content.lower()
    assert top.page_number in (1, 2)

    citation = format_document_citation(top)
    assert citation["type"] == "document"
    assert citation["file_name"] == "sample_contract.pdf"
    del current_user  # constructed to mirror real call sites; retrieve() itself is tenant-scoped


def test_retrieval_is_isolated_by_tenant(db_session):
    tenant_a, admin_a = _seed_tenant(db_session, f"a-{uuid.uuid4().hex[:8]}")
    tenant_b, admin_b = _seed_tenant(db_session, f"b-{uuid.uuid4().hex[:8]}")

    kb_a = KnowledgeBase(tenant_id=tenant_a.id, created_by=admin_a.id, name="contracts")
    db_session.add(kb_a)
    db_session.commit()

    data = SAMPLE_CONTRACT.read_bytes()
    file = upload_service.store_upload(
        db_session,
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        knowledge_base_id=kb_a.id,
        original_name="sample_contract.pdf",
        data=data,
        content_type="application/pdf",
    )
    process_file(db_session, file)

    # Tenant B searching its own (nonexistent) knowledge base id must get nothing back, even
    # though tenant A's chunks exist in the same Qdrant collection.
    results_wrong_tenant = retrieve(
        db_session, tenant_id=tenant_b.id, knowledge_base_ids=[kb_a.id], query="approved contract value"
    )
    assert results_wrong_tenant == []

    results_right_tenant = retrieve(
        db_session, tenant_id=tenant_a.id, knowledge_base_ids=[kb_a.id], query="approved contract value"
    )
    assert len(results_right_tenant) > 0


def test_reprocessing_replaces_chunks_not_duplicates(db_session):
    tenant, admin = _seed_tenant(db_session, f"re-{uuid.uuid4().hex[:8]}")
    kb = KnowledgeBase(tenant_id=tenant.id, created_by=admin.id, name="contracts")
    db_session.add(kb)
    db_session.commit()

    data = SAMPLE_CONTRACT.read_bytes()
    file = upload_service.store_upload(
        db_session,
        tenant_id=tenant.id,
        uploaded_by=admin.id,
        knowledge_base_id=kb.id,
        original_name="sample_contract.pdf",
        data=data,
        content_type="application/pdf",
    )
    process_file(db_session, file)
    db_session.expire(file)
    first_run_ids = {c.id for c in file.chunks}
    assert len(first_run_ids) > 0

    process_file(db_session, file)
    db_session.expire(file)
    second_run_ids = {c.id for c in file.chunks}

    assert len(second_run_ids) == len(first_run_ids)
    assert second_run_ids.isdisjoint(first_run_ids)  # old rows deleted, fresh ids assigned
