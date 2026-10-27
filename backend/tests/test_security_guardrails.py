import pytest
try:
    from app.auth import UserContext
    from app.executor import (
        validate_and_sanitize_command,
        execute_kubectl_command,
    )
except ImportError:
    from backend.app.auth import UserContext
    from backend.app.executor import (
        validate_and_sanitize_command,
        execute_kubectl_command,
    )

@pytest.fixture
def alice_user():
    """Alice is strictly restricted to namespace ns-4."""
    return UserContext(
        username="alice",
        allowed_namespaces=["ns-4"],
        default_namespace="ns-4",
    )

@pytest.fixture
def bob_user():
    """Bob is strictly restricted to namespace application-1."""
    return UserContext(
        username="bob",
        allowed_namespaces=["application-1"],
        default_namespace="application-1",
    )

def test_alice_allowed_command_in_ns4(alice_user):
    """Alice can run get services in ns-4."""
    args, ns = validate_and_sanitize_command("kubectl get services", alice_user, "ns-4")
    assert ns == "ns-4"
    assert args == ["kubectl", "get", "services", "--namespace", "ns-4"]

def test_alice_explicit_namespace_in_ns4(alice_user):
    """Alice can explicitly supply -n ns-4."""
    args, ns = validate_and_sanitize_command("kubectl get pods -n ns-4", alice_user, "ns-4")
    assert ns == "ns-4"
    assert "--namespace" in args
    assert "ns-4" in args

def test_alice_blocked_from_ns5(alice_user):
    """Alice must be BLOCKED if she tries to query ns-5."""
    with pytest.raises(PermissionError) as exc_info:
        validate_and_sanitize_command("kubectl get services -n ns-5", alice_user, "ns-4")
    assert "Access Denied" in str(exc_info.value)
    assert "ns-5" in str(exc_info.value)

def test_alice_blocked_from_application1(alice_user):
    """Alice must be BLOCKED if target namespace is application-1."""
    with pytest.raises(PermissionError):
        validate_and_sanitize_command("kubectl get pods", alice_user, "application-1")

def test_bob_allowed_in_application1_only(bob_user):
    """Bob can access application-1 but not ns-4."""
    args, ns = validate_and_sanitize_command("kubectl get services", bob_user, "application-1")
    assert ns == "application-1"

    with pytest.raises(PermissionError):
        validate_and_sanitize_command("kubectl get services -n ns-4", bob_user, "application-1")

def test_command_injection_chained_semicolon(alice_user):
    """Semicolon injection attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods; rm -rf /", alice_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_command_injection_pipe(alice_user):
    """Pipe injection attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods | cat /etc/passwd", alice_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_command_injection_and_and(alice_user):
    """&& chaining attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods && whoami", alice_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_all_namespaces_flag_blocked(alice_user):
    """-A and --all-namespaces flags must be blocked."""
    with pytest.raises(ValueError) as exc1:
        validate_and_sanitize_command("kubectl get pods -A", alice_user, "ns-4")
    assert "forbidden" in str(exc1.value).lower()

    with pytest.raises(ValueError) as exc2:
        validate_and_sanitize_command("kubectl get pods --all-namespaces", alice_user, "ns-4")
    assert "forbidden" in str(exc2.value).lower()

def test_destructive_verbs_blocked(alice_user):
    """Mutating commands like delete, edit, apply must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl delete pod my-pod", alice_user, "ns-4")
    assert "not permitted" in str(exc.value).lower()

def test_unauthorized_resources_blocked(alice_user):
    """Sensitive resources like secrets must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get secrets", alice_user, "ns-4")
    assert "not in the allowed list" in str(exc.value).lower()
