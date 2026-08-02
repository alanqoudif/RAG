"""API-level tests for knowledge base and file endpoints. Object storage and the Celery
dispatch are faked here (this file only exercises the HTTP/permission/DB layer); the real
end-to-end parse-chunk-embed-index pipeline against live MinIO/Qdrant is covered separately in
tests/integration/test_document_processor_live.py.
"""

import io

import pytest

from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository


class _FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def ensure_bucket(self):
        pass

    def put_object(self, object_name, data, content_type):
        self.objects[object_name] = data

    def get_object_bytes(self, object_name):
        return self.objects[object_name]

    def delete_object(self, object_name):
        self.objects.pop(object_name, None)


@pytest.fixture(autouse=True)
def _fake_storage_and_celery(monkeypatch):
    fake_storage = _FakeStorage()
    monkeypatch.setattr(
        "app.services.documents.upload_service.get_object_storage", lambda: fake_storage
    )
    monkeypatch.setattr(
        "app.api.routes.files.get_object_storage", lambda: fake_storage
    )
    monkeypatch.setattr(
        "app.api.routes.files.get_vector_store", lambda: type(
            "_Fake", (), {"delete_by_file_id": staticmethod(lambda *a, **kw: None)}
        )()
    )
    monkeypatch.setattr("app.api.routes.files.process_file_task.delay", lambda *a, **kw: None)
    monkeypatch.setattr(
        "app.api.routes.knowledge_bases.process_file_task.delay", lambda *a, **kw: None
    )
    yield fake_storage


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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_create_knowledge_base(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    response = client.post("/api/knowledge-bases", json={"name": "contracts"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "contracts"


def test_duplicate_knowledge_base_name_rejected(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    client.post("/api/knowledge-bases", json={"name": "contracts"}, headers=headers)
    response = client.post("/api/knowledge-bases", json={"name": "contracts"}, headers=headers)
    assert response.status_code == 409


def test_upload_file_via_general_endpoint(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    kb_response = client.post("/api/knowledge-bases", json={"name": "contracts"}, headers=headers)
    kb_id = kb_response.json()["id"]

    response = client.post(
        "/api/files/upload",
        files={"upload": ("sample.txt", io.BytesIO(b"hello world"), "text/plain")},
        data={"knowledge_base_id": kb_id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == "sample.txt"
    assert body["processing_status"] == "pending"
    assert body["knowledge_base_id"] == kb_id


def test_upload_unsupported_extension_rejected(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    response = client.post(
        "/api/files/upload",
        files={"upload": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 422


def test_upload_empty_file_rejected(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    response = client.post(
        "/api/files/upload",
        files={"upload": ("empty.txt", io.BytesIO(b""), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 422


def test_upload_files_into_knowledge_base_endpoint(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    kb_response = client.post("/api/knowledge-bases", json={"name": "contracts"}, headers=headers)
    kb_id = kb_response.json()["id"]

    response = client.post(
        f"/api/knowledge-bases/{kb_id}/files",
        files={"uploads": ("doc.txt", io.BytesIO(b"some content"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    assert len(response.json()) == 1
    assert response.json()[0]["knowledge_base_id"] == kb_id


def test_list_and_get_and_delete_file(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    upload_response = client.post(
        "/api/files/upload",
        files={"upload": ("sample.txt", io.BytesIO(b"hello world"), "text/plain")},
        headers=headers,
    )
    file_id = upload_response.json()["id"]

    list_response = client.get("/api/files", headers=headers)
    assert len(list_response.json()) == 1

    get_response = client.get(f"/api/files/{file_id}", headers=headers)
    assert get_response.status_code == 200

    delete_response = client.delete(f"/api/files/{file_id}", headers=headers)
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/files/{file_id}", headers=headers)
    assert missing_response.status_code == 404


def test_reprocess_file_resets_status_to_pending(client, db_session):
    headers = _seed_admin_and_login(client, db_session)
    upload_response = client.post(
        "/api/files/upload",
        files={"upload": ("sample.txt", io.BytesIO(b"hello world"), "text/plain")},
        headers=headers,
    )
    file_id = upload_response.json()["id"]

    response = client.post(f"/api/files/{file_id}/reprocess", headers=headers)
    assert response.status_code == 200
    assert response.json()["processing_status"] == "pending"


def test_tenant_isolation_on_files(client, db_session):
    headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a")
    upload_response = client.post(
        "/api/files/upload",
        files={"upload": ("sample.txt", io.BytesIO(b"hello world"), "text/plain")},
        headers=headers_a,
    )
    file_id = upload_response.json()["id"]

    headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b")
    response = client.get(f"/api/files/{file_id}", headers=headers_b)
    assert response.status_code == 404
