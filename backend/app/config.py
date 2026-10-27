import os
import secrets
from typing import List, Set

# JWT Settings
# Use environment variable if provided; otherwise dynamically generate a cryptographically secure key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))

# Default namespace for the portal
DEFAULT_NAMESPACE = os.getenv("DEFAULT_NAMESPACE", "ns-4")

# Common suggested namespaces for cluster navigation
# Note: Any namespace can be queried; these are suggestions for the UI dropdown
ALL_NAMESPACES: List[str] = [
    "ns-4",
    "default",
    "kube-system",
    "application-1",
    "application-2",
    "application-3",
    "application-8",
    "application-9",
]

# Security Guardrails:
# 1. Destructive actions are strictly blocked:
FORBIDDEN_VERBS: Set[str] = {
    "delete",
    "rm",
}

# 2. Read and diagnostic actions are allowed across all namespaces:
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
