from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "AUDIT" in response.json()["message"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_audit():
    response = client.post(
        "/api/v1/audit/",
        json={"title": "Test Audit", "target": "example.com", "status": "pending"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Audit"
    assert data["id"] == 1


def test_list_audits():
    response = client.get("/api/v1/audit/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_audit_not_found():
    response = client.get("/api/v1/audit/9999")
    assert response.status_code == 404
