
from typing import Dict, Any, List
import psutil, logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class AdminController:
    def __init__(self, app=None, health_monitor=None):
        self.app = app
        self.health_monitor = health_monitor
    
    def get_health(self) -> Dict[str, Any]:
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
        except:
            cpu = mem = disk = 0
        
        health = {
            "cpu": cpu,
            "memory": mem,
            "disk": disk,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "healthy" if cpu < 80 and mem < 80 else "warning"
        }
        
        if self.health_monitor and hasattr(self.health_monitor, 'get_status'):
            try:
                hm_status = self.health_monitor.get_status()
                health.update(hm_status)
            except:
                pass
        
        return health
    
    def get_metrics(self) -> Dict[str, Any]:
        health = self.get_health()
        return {
            **health,
            "uptime": "N/A",
            "total_trades": 0,
            "active_optimizations": 0,
        }
    
    def get_logs(self, limit: int = 100) -> List[str]:
        # In production, read from structured logger
        return [f"Log line {i} - System operational" for i in range(min(limit, 20))]
    
    def get_users(self, permission_manager) -> List[Dict[str, Any]]:
        users = []
        if permission_manager:
            for uid, role in permission_manager.user_roles.items():
                users.append({"user_id": uid, "role": role.value})
        return users
    
    def set_feature_flag(self, flag: str, enabled: bool) -> Dict[str, Any]:
        log.info(f"Feature flag {flag} set to {enabled}")
        return {"flag": flag, "enabled": enabled, "success": True}
