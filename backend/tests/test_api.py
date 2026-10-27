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

def test_login_success():
    response = client.post("/api/v1/auth/login", json={"username": "developer"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "developer"
    assert data["user"]["allowed_namespaces"] == ["*"]

def test_query_ns4_success():
    login_res = client.post("/api/v1/auth/login", json={"username": "developer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    exec_res = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "ns-4"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["exit_code"] == 0

def test_cross_namespace_allowed():
    # Anyone can access other namespaces (e.g., application-1, ns-5)
    login_res = client.post("/api/v1/auth/login", json={"username": "developer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    exec_res = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get services", "namespace": "application-1"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["exit_code"] == 0

def test_all_namespaces_flag_allowed():
    # Cluster-wide -A queries are allowed
    login_res = client.post("/api/v1/auth/login", json={"username": "developer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    exec_res = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl get pods -A", "namespace": "ns-4"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["exit_code"] == 0

def test_delete_command_blocked_via_api():
    # Guardrail: kubectl delete is blocked
    login_res = client.post("/api/v1/auth/login", json={"username": "developer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    exec_res = client.post(
        "/api/v1/cli/exec",
        json={"command": "kubectl delete pod my-pod", "namespace": "ns-4"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    body = exec_res.json()
    assert body["exit_code"] != 0
    assert "delete" in body["output"].lower() or "delete" in (body.get("error") or "").lower()

def test_list_namespaces():
    login_res = client.post("/api/v1/auth/login", json={"username": "developer"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/namespaces", headers=headers)
    assert res.status_code == 200
    assert "ns-4" in res.json()["allowed_namespaces"]
