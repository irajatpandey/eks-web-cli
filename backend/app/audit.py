import logging
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel

# Configure logger for stdout (captured by CloudWatch in EKS)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AUDIT] %(message)s",
)
audit_logger = logging.getLogger("eks_web_cli_audit")

class AuditEntry(BaseModel):
    timestamp: str
    username: str
    namespace: str
    command: str
    status: str  # "SUCCESS", "BLOCKED", "ERROR"
    exit_code: int
    duration_ms: float
    client_ip: Optional[str] = None
    detail: Optional[str] = None

# In-memory buffer of recent audit entries for UI display
MAX_AUDIT_LOGS = 200
_audit_logs: List[AuditEntry] = []

def record_audit(
    username: str,
    namespace: str,
    command: str,
    status: str,
    exit_code: int,
    duration_ms: float,
    client_ip: Optional[str] = None,
    detail: Optional[str] = None,
) -> AuditEntry:
    """Records an audit event to logger (CloudWatch) and circular memory buffer."""
    now_iso = datetime.now(timezone.utc).isoformat()
    entry = AuditEntry(
        timestamp=now_iso,
        username=username,
        namespace=namespace,
        command=command,
        status=status,
        exit_code=exit_code,
        duration_ms=round(duration_ms, 2),
        client_ip=client_ip,
        detail=detail,
    )
    
    # CloudWatch log line
    audit_logger.info(
        f"user={username} namespace={namespace} status={status} code={exit_code} "
        f"duration={duration_ms:.1f}ms ip={client_ip} cmd=\"{command}\" detail=\"{detail or ''}\""
    )
    
    _audit_logs.append(entry)
    if len(_audit_logs) > MAX_AUDIT_LOGS:
        _audit_logs.pop(0)
        
    return entry

def get_audit_logs(
    namespace: Optional[str] = None,
    username: Optional[str] = None,
    limit: int = 50,
) -> List[AuditEntry]:
    """Retrieves recent audit logs filtered by namespace or username."""
    filtered = _audit_logs
    if namespace:
        filtered = [l for l in filtered if l.namespace == namespace]
    if username:
        filtered = [l for l in filtered if l.username == username]
    return list(reversed(filtered[-limit:]))
