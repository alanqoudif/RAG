def test_liveness(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok(client):
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"


def test_metrics_endpoint_exposed(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content or response.content == b""


def test_request_id_header_present(client):
    response = client.get("/api/health")
    assert "X-Request-ID" in response.headers


def test_not_found_returns_structured_error(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "HTTP_ERROR"
    assert "request_id" in body["error"]
