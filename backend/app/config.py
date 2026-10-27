import os
import secrets
from typing import List, Dict, Set

# JWT Settings
# Use environment variable if provided; otherwise dynamically generate a cryptographically secure key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))

# Namespaces configured for the cluster
ALL_NAMESPACES: List[str] = [
    "ns-4",
    "ns-5",
    "ns-6",
    "application-1",
    "application-2",
    "application-3",
    "application-8",
    "application-9",
]

# Predefined user to allowed namespaces mapping
# In production, this can also be loaded from AWS Cognito claims, Okta groups, or a K8s ConfigMap
USER_NAMESPACE_MAP: Dict[str, List[str]] = {
    "alice": ["ns-4"],
    "bob": ["application-1"],
    "carol": ["ns-5", "ns-6"],
    "dave": ["application-2", "application-3"],
    "qa-user": ["application-8", "application-9"],
    "devops-viewer": ALL_NAMESPACES,
}

# RBAC Command Whitelist
ALLOWED_VERBS: Set[str] = {
    "get",
    "describe",
    "logs",
    "top",
}

ALLOWED_RESOURCES: Set[str] = {
    "services", "service", "svc",
    "pods", "pod", "po",
    "deployments", "deployment", "deploy",
    "endpoints", "endpoint", "ep",
    "configmaps", "configmap", "cm",
    "ingresses", "ingress", "ing",
    "events", "ev",
    "replicasets", "replicaset", "rs",
}

# Flags that are strictly forbidden (could breach namespace isolation or escalate privileges)
FORBIDDEN_FLAGS: Set[str] = {
    "-A",
    "--all-namespaces",
    "--kubeconfig",
    "--context",
    "--cluster",
    "--token",
    "--as",
    "--as-group",
    "--server",
}
