"""
Audit logging for RBAC access.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import structlog

logger = structlog.get_logger()


class AuditLogger:
    """Audit logger for RBAC access events."""
    
    def __init__(self):
        self.enabled = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
        self.log_dir = Path(os.getenv("AUDIT_LOG_DIR", "/var/log/audit"))
        self.log_file = self.log_dir / "access.log"
        
        # Create log directory if it doesn't exist
        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def log(
        self,
        user_id: str,
        user_name: str,
        roles: List[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        allowed: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log an audit event."""
        if not self.enabled:
            return
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "user_name": user_name,
            "roles": roles,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": "allowed" if allowed else "denied",
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        
        try:
            # Write to file
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")
            
            # Also log to structured logger
            logger.info(
                "Audit event",
                **event
            )
        except Exception as e:
            logger.error("Audit logging failed", error=str(e))
    
    async def query(
        self,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        allowed: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit logs."""
        if not self.log_file.exists():
            return []
        
        results = []
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    event = json.loads(line)
                    
                    # Filter
                    if user_id and event.get("user_id") != user_id:
                        continue
                    if resource_type and event.get("resource_type") != resource_type:
                        continue
                    if action and event.get("action") != action:
                        continue
                    if allowed is not None:
                        event_allowed = event.get("result") == "allowed"
                        if event_allowed != allowed:
                            continue
                    
                    results.append(event)
                    
                    if len(results) >= limit:
                        break
            
            # Sort by timestamp descending
            results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
        except Exception as e:
            logger.error("Audit query failed", error=str(e))
        
        return results

