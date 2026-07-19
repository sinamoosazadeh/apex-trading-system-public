
from __future__ import annotations
from enum import Enum
from typing import Dict, Set, List
import logging

log = logging.getLogger(__name__)

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

# Permission matrix per blueprint Part 14
PERMISSIONS: Dict[Role, Set[str]] = {
    Role.OWNER: {
        "all",  # Everything
        "trading.live.start", "trading.live.stop", "trading.live.emergency",
        "optimization.run", "optimization.rollback", "optimization.delete",
        "admin.users", "admin.vault", "admin.factory_reset", "admin.features",
        "admin.logs", "admin.health", "admin.shutdown",
        "portfolio.view", "portfolio.export", "portfolio.manage",
        "backtest.run", "backtest.view", "backtest.export",
        "reports.view", "reports.export", "reports.delete",
        "settings.general", "settings.risk", "settings.notifications",
        "market.view",
    },
    Role.ADMIN: {
        "trading.live.start", "trading.live.stop", "trading.live.emergency",
        "trading.paper.start", "trading.paper.stop",
        "optimization.run", "optimization.rollback", "optimization.view", "optimization.list",
        "portfolio.view", "portfolio.export",
        "backtest.run", "backtest.view", "backtest.export",
        "reports.view", "reports.export",
        "settings.view", "market.view", "status.view",
    },
    Role.ANALYST: {
        "backtest.run", "backtest.view", "backtest.export",
        "optimization.view", "optimization.list",
        "portfolio.view",
        "reports.view", "reports.export",
        "market.view", "status.view",
        "trading.paper.view", "trading.paper.signals",
    },
    Role.VIEWER: {
        "status.view", "portfolio.view", "market.view",
        "reports.view", "backtest.view",
    }
}

class PermissionManager:
    """RBAC per blueprint - Zero Trust"""
    def __init__(self, owner_ids: List[int] = None, admin_ids: List[int] = None):
        self.owner_ids = set(owner_ids or [])
        self.admin_ids = set(admin_ids or [])
        self.user_roles: Dict[int, Role] = {}
        # Set owners
        for oid in self.owner_ids:
            self.user_roles[oid] = Role.OWNER
        for aid in self.admin_ids:
            if aid not in self.user_roles:
                self.user_roles[aid] = Role.ADMIN
    
    def get_role(self, user_id: int) -> Role:
        if user_id in self.user_roles:
            return self.user_roles[user_id]
        if user_id in self.owner_ids:
            return Role.OWNER
        if user_id in self.admin_ids:
            return Role.ADMIN
        return Role.VIEWER
    
    def set_role(self, user_id: int, role: Role, setter_id: int) -> bool:
        setter_role = self.get_role(setter_id)
        # Only owner can set roles, admin can set analyst/viewer
        if setter_role == Role.OWNER:
            self.user_roles[user_id] = role
            if role == Role.OWNER:
                self.owner_ids.add(user_id)
            elif role == Role.ADMIN:
                self.admin_ids.add(user_id)
            log.info(f"Role set: user {user_id} -> {role.value} by {setter_id}")
            return True
        elif setter_role == Role.ADMIN and role in [Role.ANALYST, Role.VIEWER]:
            self.user_roles[user_id] = role
            return True
        return False
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        role = self.get_role(user_id)
        perms = PERMISSIONS.get(role, set())
        if "all" in perms:
            return True
        # Check exact and wildcard
        if permission in perms:
            return True
        # Check prefix wildcard e.g. backtest.* covers backtest.run
        for perm in perms:
            if perm.endswith(".*") and permission.startswith(perm[:-2]):
                return True
            if permission.startswith(perm + "."):
                return True
        return False
    
    def is_admin(self, user_id: int) -> bool:
        return self.get_role(user_id) in [Role.OWNER, Role.ADMIN]
    
    def is_owner(self, user_id: int) -> bool:
        return self.get_role(user_id) == Role.OWNER
    
    def check_and_log(self, user_id: int, permission: str, resource: str = "") -> bool:
        has = self.has_permission(user_id, permission)
        if not has:
            log.warning(f"Permission denied: user {user_id} role {self.get_role(user_id).value} tried {permission} on {resource}")
        return has
