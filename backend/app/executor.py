import os
import re
import shlex
import subprocess
import time
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel

from .config import (
    ALLOWED_VERBS,
    FORBIDDEN_VERBS,
    FORBIDDEN_FLAGS,
)
from .auth import UserContext
from .audit import record_audit

class ExecutionResult(BaseModel):
    command_executed: str
    namespace_used: str
    output: str
    exit_code: int
    duration_ms: float
    is_mock: bool = False
    error: Optional[str] = None

# Characters that attempt shell chaining, injection, or redirection
DANGEROUS_SHELL_CHARS = [";", "&&", "||", "|", ">", "<", "`", "$", "\n", "\r", "&"]

# Mock data store for offline / local testing when cluster is disconnected
MOCK_RESOURCES = {
    "ns-4": {
        "services": """NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
order-service     ClusterIP   10.100.14.22     <none>        80/TCP           4d12h
catalog-service   ClusterIP   10.100.45.88     <none>        8080/TCP         4d12h
inventory-api     ClusterIP   10.100.72.19     <none>        9000/TCP         2d""",
        "pods": """NAME                               READY   STATUS    RESTARTS   AGE
order-service-6d8b8-x7q9w          1/1     Running   0          4d12h
order-service-6d8b8-p2lk4          1/1     Running   0          4d12h
catalog-service-4f1a2-9mzp1        1/1     Running   0          4d12h
inventory-api-7b99c-v8r12          1/1     Running   0          2d""",
        "deployments": """NAME              READY   UP-TO-DATE   AVAILABLE   AGE
order-service     2/2     2            2           4d12h
catalog-service   1/1     1            1           4d12h
inventory-api     1/1     1            1           2d""",
        "endpoints": """NAME              ENDPOINTS                                   AGE
order-service     10.0.1.42:80,10.0.2.19:80                   4d12h
catalog-service   10.0.1.88:8080                              4d12h
inventory-api     10.0.3.14:9000                              2d""",
    },
    "application-1": {
        "services": """NAME               TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
auth-service       ClusterIP   10.100.102.15    <none>        443/TCP          6d
user-profile-svc   ClusterIP   10.100.108.92    <none>        8080/TCP         5d""",
        "pods": """NAME                               READY   STATUS    RESTARTS   AGE
auth-service-79f8c-ab312           1/1     Running   0          6d
user-profile-svc-54dd9-q11x9       1/1     Running   0          5d""",
        "deployments": """NAME               READY   UP-TO-DATE   AVAILABLE   AGE
auth-service       1/1     1            1           6d
user-profile-svc   1/1     1            1           5d""",
        "endpoints": """NAME               ENDPOINTS                  AGE
auth-service       10.0.2.77:443              6d
user-profile-svc   10.0.2.99:8080             5d""",
    },
    "application-2": {
        "services": """NAME               TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
payment-gateway    ClusterIP   10.100.201.5     <none>        8443/TCP         10d
checkout-api       ClusterIP   10.100.204.33    <none>        80/TCP           8d""",
        "pods": """NAME                               READY   STATUS    RESTARTS   AGE
payment-gateway-698b-kl391         1/1     Running   0          10d
checkout-api-5c12e-ww812           1/1     Running   0          8d""",
        "deployments": """NAME               READY   UP-TO-DATE   AVAILABLE   AGE
payment-gateway    1/1     1            1           10d
checkout-api       1/1     1            1           8d""",
        "endpoints": """NAME               ENDPOINTS                  AGE
payment-gateway    10.0.4.12:8443             10d
checkout-api       10.0.4.88:80               8d""",
    },
    "ns-5": {
        "services": """NAME                  TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
analytics-collector   ClusterIP   10.100.155.10    <none>        9200/TCP   1d""",
        "pods": """NAME                                  READY   STATUS    RESTARTS   AGE
analytics-collector-8bc11-j4481       1/1     Running   0          1d""",
        "deployments": """NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
analytics-collector   1/1     1            1           1d""",
        "endpoints": """NAME                  ENDPOINTS             AGE
analytics-collector   10.0.5.21:9200        1d""",
    },
}

def validate_and_sanitize_command(
    raw_command: str,
    user: UserContext,
    target_namespace: str,
) -> Tuple[List[str], str]:
    """
    Validates that the command:
    1. Contains no shell injection / chaining characters.
    2. Strictly forbids destructive actions like 'delete'.
    3. Allows read and diagnostic actions across ANY namespace.
    4. Supports cluster-wide queries (-A, --all-namespaces).
    
    Returns: (sanitized_args_list, effective_namespace)
    """
    raw_cmd = raw_command.strip()
    if not raw_cmd:
        raise ValueError("Command cannot be empty.")
        
    # Check 1: Command injection prevention
    for bad_char in DANGEROUS_SHELL_CHARS:
        if bad_char in raw_cmd:
            raise ValueError(
                f"Security violation: Illegal character '{bad_char}' detected. "
                "Shell chaining, redirection, and variable expansion are strictly forbidden."
            )
            
    # Tokenize command safely
    try:
        tokens = shlex.split(raw_cmd)
    except Exception as e:
        raise ValueError(f"Malformed command syntax: {str(e)}")
        
    if not tokens:
        raise ValueError("Command cannot be empty.")
        
    # Normalize command starting token: accept 'kubectl', 'k', or implied verb
    if tokens[0] in ("kubectl", "k"):
        tokens = tokens[1:]
        
    if not tokens:
        raise ValueError("Missing kubectl action (e.g., 'get pods', 'describe service').")
        
    verb = tokens[0].lower()
    
    # Check 2: Guardrail - strictly block delete commands
    if verb in FORBIDDEN_VERBS or verb == "delete":
        raise ValueError(
            "Guardrail violation: Action 'delete' is strictly forbidden. Mutating resource deletion is blocked."
        )
        
    # Check 3: Allowed actions
    if verb not in ALLOWED_VERBS:
        raise ValueError(
            f"Action '{verb}' is not permitted. Allowed actions: {', '.join(sorted(ALLOWED_VERBS))}."
        )
        
    # Check 4: Forbidden flags (credential / cluster tampering)
    for token in tokens:
        if token in FORBIDDEN_FLAGS:
            raise ValueError(
                f"Flag '{token}' is forbidden for security reasons."
            )
            
    # Check 5: Extract namespace from user input (supports -A, --all-namespaces, -n, --namespace)
    is_all_namespaces = False
    extracted_ns: Optional[str] = None
    cleaned_tokens: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("-A", "--all-namespaces"):
            is_all_namespaces = True
            cleaned_tokens.append(t)
            i += 1
            continue
        elif t in ("-n", "--namespace"):
            if i + 1 < len(tokens):
                extracted_ns = tokens[i + 1]
                i += 2
                continue
            else:
                raise ValueError("Flag -n/--namespace requires an argument.")
        elif t.startswith("-n="):
            extracted_ns = t.split("=", 1)[1]
            i += 1
            continue
        elif t.startswith("--namespace="):
            extracted_ns = t.split("=", 1)[1]
            i += 1
            continue
        else:
            cleaned_tokens.append(t)
            i += 1
            
    # Effective namespace: Anyone can access any namespace!
    if is_all_namespaces:
        effective_ns = "all-namespaces"
        final_args = ["kubectl", verb] + cleaned_tokens[1:]
    else:
        effective_ns = extracted_ns if extracted_ns else (target_namespace or "default")
        final_args = ["kubectl", verb] + cleaned_tokens[1:] + ["--namespace", effective_ns]
        
    return final_args, effective_ns


def execute_kubectl_command(
    raw_command: str,
    user: UserContext,
    target_namespace: str,
    client_ip: Optional[str] = None,
) -> ExecutionResult:
    """Executes the validated kubectl command within the target namespace."""
    start_time = time.time()
    
    try:
        final_args, effective_ns = validate_and_sanitize_command(
            raw_command, user, target_namespace
        )
    except (ValueError, PermissionError) as e:
        duration_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        record_audit(
            username=user.username,
            namespace=target_namespace,
            command=raw_command,
            status="BLOCKED",
            exit_code=1,
            duration_ms=duration_ms,
            client_ip=client_ip,
            detail=error_msg,
        )
        return ExecutionResult(
            command_executed=raw_command,
            namespace_used=target_namespace,
            output="",
            exit_code=1,
            duration_ms=duration_ms,
            error=error_msg,
        )

    cmd_display = " ".join(final_args)
    
    # Attempt real execution with kubectl in the Pod
    try:
        proc = subprocess.run(
            final_args,
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,  # CRITICAL: shell=False prevents shell injection
        )
        duration_ms = (time.time() - start_time) * 1000
        
        # Check if real cluster responded or if connection failed
        output = proc.stdout if proc.returncode == 0 else proc.stderr
        
        # If connection refused or no cluster reachable, provide realistic fallback response
        # so local testing without a live cluster works seamlessly
        is_mock = False
        if proc.returncode != 0 and (
            "connection refused" in output.lower()
            or "unable to connect" in output.lower()
            or "no configuration has been provided" in output.lower()
        ):
            output, exit_code, is_mock = generate_mock_output(final_args, effective_ns)
            status_str = "SUCCESS" if exit_code == 0 else "ERROR"
        else:
            exit_code = proc.returncode
            status_str = "SUCCESS" if exit_code == 0 else "ERROR"

        record_audit(
            username=user.username,
            namespace=effective_ns,
            command=cmd_display,
            status=status_str,
            exit_code=exit_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )
        
        return ExecutionResult(
            command_executed=cmd_display,
            namespace_used=effective_ns,
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            is_mock=is_mock,
        )
        
    except FileNotFoundError:
        # kubectl executable not installed in host environment; use mock fallback
        duration_ms = (time.time() - start_time) * 1000
        output, exit_code, is_mock = generate_mock_output(final_args, effective_ns)
        record_audit(
            username=user.username,
            namespace=effective_ns,
            command=cmd_display,
            status="SUCCESS",
            exit_code=exit_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            detail="Ran in fallback simulation mode",
        )
        return ExecutionResult(
            command_executed=cmd_display,
            namespace_used=effective_ns,
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            is_mock=is_mock,
        )
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start_time) * 1000
        err_msg = "Command timed out after 15 seconds."
        record_audit(
            username=user.username,
            namespace=effective_ns,
            command=cmd_display,
            status="ERROR",
            exit_code=124,
            duration_ms=duration_ms,
            client_ip=client_ip,
            detail=err_msg,
        )
        return ExecutionResult(
            command_executed=cmd_display,
            namespace_used=effective_ns,
            output="",
            exit_code=124,
            duration_ms=duration_ms,
            error=err_msg,
        )


def generate_mock_output(args: List[str], namespace: str) -> Tuple[str, int, bool]:
    """Generates realistic Kubernetes CLI output for offline / local testing."""
    verb = args[1] if len(args) > 1 else "get"
    resource = args[2] if len(args) > 2 else "services"
    
    # Normalize resource name
    res_key = "services"
    if resource in ("pods", "pod", "po"):
        res_key = "pods"
    elif resource in ("deployments", "deployment", "deploy"):
        res_key = "deployments"
    elif resource in ("endpoints", "endpoint", "ep"):
        res_key = "endpoints"
        
    ns_data = MOCK_RESOURCES.get(namespace, {})
    if res_key in ns_data:
        return ns_data[res_key], 0, True
        
    # Default message for namespaces without predefined mock data
    if verb == "get":
        return f"No resources found in {namespace} namespace.", 0, True
    elif verb == "describe":
        return f"Name:             sample-{res_key}\nNamespace:        {namespace}\nLabels:           app=sample\nStatus:           Active", 0, True
    elif verb == "logs":
        return f"[2026-10-27T19:40:00Z] Info: {namespace} service initialized successfully.\n[2026-10-27T19:42:15Z] HTTP 200 GET /healthz 1.2ms", 0, True
    else:
        return f"Simulated output for {verb} {resource} in namespace {namespace}", 0, True
