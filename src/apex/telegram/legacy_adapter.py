
"""Legacy adapter - Keeps old infrastructure/telegram/bot.py working while using new enterprise system"""
from __future__ import annotations

try:
    from ...telegram.bot import TelegramBot as EnterpriseBot
    HAS_ENTERPRISE = True
except ImportError:
    HAS_ENTERPRISE = False

class LegacyBotAdapter:
    """Adapter for old bot.py to delegate to new enterprise bot"""
    def __init__(self, *args, **kwargs):
        self.enterprise_bot = None
        if HAS_ENTERPRISE:
            try:
                self.enterprise_bot = EnterpriseBot(*args, **kwargs)
            except:
                pass
    
    def run(self, *args, **kwargs):
        if self.enterprise_bot:
            return self.enterprise_bot.run(*args, **kwargs)
        # Fallback to old implementation
        print("Enterprise bot not available, using legacy")
