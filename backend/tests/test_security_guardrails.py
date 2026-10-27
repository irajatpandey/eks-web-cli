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
def test_user():
    """Generic operator user with universal cluster access."""
    return UserContext(
        username="developer",
        allowed_namespaces=["*"],
        default_namespace="ns-4",
    )

def test_delete_command_strictly_blocked(test_user):
    """Guardrail: kubectl delete commands must be strictly BLOCKED."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl delete pod my-pod", test_user, "ns-4")
    assert "delete" in str(exc.value).lower()
    assert "forbidden" in str(exc.value).lower()

def test_delete_with_namespace_blocked(test_user):
    """Guardrail: delete commands in any namespace must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl delete svc my-service -n application-1", test_user, "application-1")
    assert "delete" in str(exc.value).lower()

def test_short_k_delete_blocked(test_user):
    """Guardrail: 'k delete' alias must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("k delete deployment order-service", test_user, "ns-4")
    assert "delete" in str(exc.value).lower()

def test_allowed_command_in_ns4(test_user):
    """User can query resources in ns-4."""
    args, ns = validate_and_sanitize_command("kubectl get services", test_user, "ns-4")
    assert ns == "ns-4"
    assert args == ["kubectl", "get", "services", "--namespace", "ns-4"]

def test_allowed_cross_namespace_access(test_user):
    """Anyone can access any namespace: application-1, ns-5, etc."""
    args, ns = validate_and_sanitize_command("kubectl get services -n application-1", test_user, "ns-4")
    assert ns == "application-1"
    assert "--namespace" in args
    assert "application-1" in args

def test_allowed_custom_namespace(test_user):
    """Anyone can access arbitrary custom namespaces."""
    args, ns = validate_and_sanitize_command("kubectl get pods -n custom-team-ns", test_user, "default")
    assert ns == "custom-team-ns"
    assert args == ["kubectl", "get", "pods", "--namespace", "custom-team-ns"]

def test_all_namespaces_flag_allowed(test_user):
    """Cluster-wide queries with -A and --all-namespaces are explicitly ALLOWED."""
    args1, ns1 = validate_and_sanitize_command("kubectl get pods -A", test_user, "ns-4")
    assert ns1 == "all-namespaces"
    assert "-A" in args1

    args2, ns2 = validate_and_sanitize_command("kubectl get services --all-namespaces", test_user, "ns-4")
    assert ns2 == "all-namespaces"
    assert "--all-namespaces" in args2

def test_command_injection_chained_semicolon(test_user):
    """Semicolon injection attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods; rm -rf /", test_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_command_injection_pipe(test_user):
    """Pipe injection attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods | cat /etc/passwd", test_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_command_injection_and_and(test_user):
    """&& chaining attempts must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods && whoami", test_user, "ns-4")
    assert "Illegal character" in str(exc.value)

def test_credential_tampering_flags_blocked(test_user):
    """Flags that tamper with kubeconfig or cluster tokens must be blocked."""
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_command("kubectl get pods --kubeconfig /tmp/fake", test_user, "ns-4")
    assert "forbidden" in str(exc.value).lower()
