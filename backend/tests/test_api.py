import pytest
from fastapi.testclient import TestClient
try:
    from app.main import app
except ImportError:
    from backend.app.main import app

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_login_alice_success():
    response = client.post("/api/v1/auth/login", json={"username": "alice"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"
    assert data["user"]["allowed_namespaces"] == ["ns-4"]

def test_login_invalid_user():
    response = client.post("/api/v1/auth/login", json={"username": "unknown_user"})
    assert response.status_code == 401

def test_alice_cannot_query_application1():
    # Login as Alice
    login_res = client.post("/api/v1/auth/login", json={"username": "alice"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query allowed namespace ns-4: should succeed
    exec_res_ns4 = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "ns-4"},
        headers=headers,
    )
    assert exec_res_ns4.status_code == 200
    assert exec_res_ns4.json()["exit_code"] == 0

    # Query unauthorized namespace application-1: should return 403 Forbidden
    exec_res_app1 = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "application-1"},
        headers=headers,
    )
    assert exec_res_app1.status_code == 403
    assert "Access Denied" in exec_res_app1.json()["detail"]

def test_bob_authorized_for_application1():
    # Login as Bob
    login_res = client.post("/api/v1/auth/login", json={"username": "bob"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query application-1: should succeed
    exec_res = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "application-1"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["exit_code"] == 0

    # Query ns-4: should be rejected with 403
    exec_res_ns4 = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "ns-4"},
        headers=headers,
    )
    assert exec_res_ns4.status_code == 403
