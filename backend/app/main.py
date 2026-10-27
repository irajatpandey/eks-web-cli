import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import USER_NAMESPACE_MAP
from .auth import (
    UserContext,
    LoginRequest,
    TokenResponse,
    authenticate_user,
    create_access_token,
    get_current_user,
)
from .executor import execute_kubectl_command, ExecutionResult
from .audit import get_audit_logs, AuditEntry

app = FastAPI(
    title="AWS EKS Web CLI - Scoped Access Portal",
    description="Secure, namespace-isolated Web CLI for AWS EKS without cluster-admin privileges.",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandRequest(BaseModel):
    command: str
    namespace: str

class NamespaceListResponse(BaseModel):
    username: str
    allowed_namespaces: List[str]
    active_namespace: str

# API Routes
@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticates the user and returns a signed JWT with scoped namespaces."""
    user = authenticate_user(req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown or unauthorized user. Configured users: alice, bob, carol, dave, qa-user, devops-viewer.",
        )
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=user)

@app.get("/api/v1/auth/me", response_model=UserContext)
async def get_current_user_profile(user: UserContext = Depends(get_current_user)):
    """Returns the authenticated user's profile and allowed namespaces."""
    return user

@app.get("/api/v1/namespaces", response_model=NamespaceListResponse)
async def list_user_namespaces(user: UserContext = Depends(get_current_user)):
    """Returns the list of namespaces the authenticated user is allowed to access."""
    return NamespaceListResponse(
        username=user.username,
        allowed_namespaces=user.allowed_namespaces,
        active_namespace=user.default_namespace,
    )

@app.post("/api/v1/cli/exec", response_model=ExecutionResult)
async def execute_command(
    req: CommandRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Executes a kubectl command securely scoped to the user's namespace.
    Strictly forbids accessing unauthorized namespaces or using cluster-wide flags.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Boundary check: ensure target namespace is in user's allowed list
    if req.namespace not in user.allowed_namespaces:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: You do not have permission to access namespace '{req.namespace}'. "
                   f"Your authorized namespaces: {', '.join(user.allowed_namespaces)}",
        )
        
    result = execute_kubectl_command(
        raw_command=req.command,
        user=user,
        target_namespace=req.namespace,
        client_ip=client_ip,
    )
    return result

@app.get("/api/v1/audit/logs", response_model=List[AuditEntry])
async def fetch_audit_logs(
    namespace: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
):
    """Fetches audit logs filtered by the user's allowed namespaces."""
    # Enforce namespace isolation on audit logs as well
    if namespace and namespace not in user.allowed_namespaces:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: You cannot view audit logs for namespace '{namespace}'.",
        )
        
    # If no namespace specified, pick first allowed namespace
    ns_to_query = namespace or user.default_namespace
    return get_audit_logs(namespace=ns_to_query)

@app.get("/healthz")
async def health_check():
    """Kubernetes liveness and readiness probe endpoint."""
    return {"status": "ok", "service": "eks-web-cli"}

# Mount frontend directory for static UI serving
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Frontend index.html not found"}
