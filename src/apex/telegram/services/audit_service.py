
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
import json, logging

log = logging.getLogger(__name__)

class AuditService:
    """Audit Trail per blueprint Part 14"""
    
    def __init__(self, base_path: str = "audit_logs"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_path / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    
    def log(self, user_id: int, username: str, role: str, action: str, params: Dict[str, Any], result: str = "success", old_state: str = "", new_state: str = "", duration_ms: int = 0, chat_id: int = 0):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "username": username,
            "role": role,
            "chat_id": chat_id,
            "action": action,
            "params": params,
            "old_state": old_state,
            "new_state": new_state,
            "result": result,
            "duration_ms": duration_ms,
            "correlation_id": f"{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        }
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.error(f"Audit log failed: {e}")
        log.info(f"AUDIT: {username} ({role}) - {action} - {result}")
        return entry
    
    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        entries = []
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        try:
                            entries.append(json.loads(line))
                        except:
                            pass
        except:
            pass
        return entries
    
    def get_user_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        all_entries = self.get_recent(1000)
        return [e for e in all_entries if e.get('user_id') == user_id][-limit:]
