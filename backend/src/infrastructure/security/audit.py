import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.infrastructure.security.jwt import TokenData

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = LOG_DIR / "audit.log"

_audit_logger = logging.getLogger("web2r.audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False

if not _audit_logger.handlers:
    _handler = RotatingFileHandler(
        AUDIT_LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_handler)


def audit_log(
    action: str,
    target_entity: str,
    target_id: int | str | None = None,
    actor: TokenData | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Emits an immutable structured JSON audit entry conforming to ISO 27001 A.8.15 & SOC 2 CC7.2."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action,
        "target_entity": target_entity,
        "target_id": str(target_id) if target_id is not None else None,
        "actor_id": actor.user_id if actor else None,
        "actor_email": actor.email if actor else "anonymous",
        "actor_role": actor.role.value if actor else None,
        "ip_address": ip_address or "internal",
        "details": details or {},
    }
    _audit_logger.info(json.dumps(entry, ensure_ascii=False))
