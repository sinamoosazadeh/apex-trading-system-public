
"""APEX Telegram Enterprise Control Center - Per Blueprint"""
from .core.session import SessionManager, TelegramSession
from .core.permissions import PermissionManager, Role
from .core.state_machine import StateMachine, MenuState
from .core.router import CallbackRouter, MessageRouter
from .bot import TelegramBot
from .integration import integrate_telegram_system

__all__ = [
    "SessionManager", "TelegramSession",
    "PermissionManager", "Role",
    "StateMachine", "MenuState",
    "CallbackRouter", "MessageRouter",
    "TelegramBot", "integrate_telegram_system"
]

def get_bot(token: str = "", app=None, owner_ids=None, admin_ids=None):
    return TelegramBot(token=token, app=app, owner_ids=owner_ids, admin_ids=admin_ids)
