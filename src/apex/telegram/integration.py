
from __future__ import annotations
import logging
from typing import List

log = logging.getLogger(__name__)

def integrate_telegram_system(app, token: str = "", owner_ids: List[int] = None, admin_ids: List[int] = None):
    """Integrate new Telegram Enterprise Control Center without breaking existing bot.py"""
    try:
        from .bot import TelegramBot
        
        # Get token from vault if not provided
        if not token and app:
            try:
                if hasattr(app, 'vault'):
                    token = app.vault.get_secret("telegram_bot_token") or app.vault.get_secret("TELEGRAM_BOT_TOKEN") or ""
            except:
                pass
        
        bot = TelegramBot(token=token, app=app, owner_ids=owner_ids, admin_ids=admin_ids)
        
        # Attach to app
        if app:
            app.telegram_bot = bot
            app.telegram_enterprise = bot
            app.session_manager = bot.session_manager
            app.permission_manager = bot.permission_manager
            app.notification_service = bot.notification_service
            app.audit_service = bot.audit_service
        
        log.info("✅ Telegram Enterprise Control Center integrated - 8 subsystems, 14 menus, RBAC, Session, Audit")
        return bot
    except Exception as e:
        log.warning(f"Telegram integration failed (non-critical): {e}")
        return None
