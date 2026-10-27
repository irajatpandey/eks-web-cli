from datetime import datetime, timedelta, timezone
from typing import List, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
    DEFAULT_NAMESPACE,
)

security = HTTPBearer()

class UserContext(BaseModel):
    username: str
    allowed_namespaces: List[str] = ["*"]
    default_namespace: str = DEFAULT_NAMESPACE

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserContext

class LoginRequest(BaseModel):
    username: Optional[str] = "operator"

def authenticate_user(username: Optional[str] = None) -> UserContext:
    """Authenticates user with cluster-wide namespace access."""
    clean_username = (username or "operator").strip()
    if not clean_username:
        clean_username = "operator"
        
    return UserContext(
        username=clean_username,
        allowed_namespaces=["*"],
        default_namespace=DEFAULT_NAMESPACE,
    )

def create_access_token(user: UserContext) -> str:
    """Generates a signed JWT with user identity."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": user.username,
        "namespaces": user.allowed_namespaces,
        "default_ns": user.default_namespace,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> UserContext:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub", "operator")
        namespaces: List[str] = payload.get("namespaces", ["*"])
        default_ns: str = payload.get("default_ns", DEFAULT_NAMESPACE)
        return UserContext(
            username=username,
            allowed_namespaces=namespaces if namespaces else ["*"],
            default_namespace=default_ns,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate token: {str(e)}",
        )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserContext:
    """FastAPI dependency to extract and validate the authenticated user."""
    return decode_access_token(credentials.credentials)
