import os
import secrets
from pathlib import Path
from typing import List, Set

# JWT Settings
# Use environment variable if provided; otherwise dynamically generate a cryptographically secure key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))

def detect_namespace() -> str:
    """
    Auto-detects the deployed namespace:
    1. Downward API environment variable (POD_NAMESPACE)
    2. Kubernetes in-cluster ServiceAccount namespace file
    3. DEFAULT_NAMESPACE environment variable or fallback to 'ns-4'
    """
    if os.getenv("POD_NAMESPACE"):
        return os.getenv("POD_NAMESPACE").strip()
    sa_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    if sa_path.exists():
        try:
            return sa_path.read_text().strip()
        except Exception:
            pass
    return os.getenv("DEFAULT_NAMESPACE", "ns-4").strip()

# Target namespace where this backend instance is deployed
DEFAULT_NAMESPACE = detect_namespace()

# Namespaces available for selection in the Web CLI UI
# Can be overridden with MANAGED_NAMESPACES="ns-4,application-1,application-2"
configured_ns = os.getenv("MANAGED_NAMESPACES", "")
if configured_ns:
    ALL_NAMESPACES: List[str] = [ns.strip() for ns in configured_ns.split(",") if ns.strip()]
else:
    ALL_NAMESPACES: List[str] = [DEFAULT_NAMESPACE, "application-1", "application-2", "application-3"]

# Security Guardrails:
# 1. Destructive actions are strictly blocked:
FORBIDDEN_VERBS: Set[str] = {
    "delete",
    "rm",
}

# 2. Read and diagnostic actions are allowed:
ALLOWED_VERBS: Set[str] = {
    "get",
    "describe",
    "logs",
    "top",
    "explain",
    "version",
    "api-resources",
    "cluster-info",
    "diff",
}

# 3. Flags that attempt credential or cluster tampering are blocked:
FORBIDDEN_FLAGS: Set[str] = {
    "--kubeconfig",
    "--context",
    "--cluster",
    "--token",
    "--as",
    "--as-group",
    "--server",
}
