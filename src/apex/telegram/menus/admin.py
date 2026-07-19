
from ..utils.keyboard_builder import KeyboardBuilder

class AdminMenu:
    @staticmethod
    def main_menu(is_owner: bool = False):
        buttons = [
            [{"text": "❤️ Health", "callback": "admin.health"}, {"text": "📊 Metrics", "callback": "admin.metrics"}],
            [{"text": "📋 Logs", "callback": "admin.logs"}, {"text": "👥 Users", "callback": "admin.users"}],
            [{"text": "⚙ Features", "callback": "admin.features"}, {"text": "🔧 Settings", "callback": "admin.settings"}],
            [{"text": "🚨 Emergency", "callback": "admin.emergency"}],
        ]
        if is_owner:
            buttons.append([{"text": "💀 Factory Reset", "callback": "admin.factory_reset.confirm"}])
        
        return {
            "message": f"""🛡 **ADMIN PANEL**

{'👑 Owner Access' if is_owner else '🔧 Admin Access'}

• Health - System health, heartbeats
• Metrics - CPU, memory, performance
• Logs - Recent logs & audit
• Users - Manage roles
• Features - Feature flags
• Emergency - Global emergency stop

All actions audited.
""",
            "keyboard": KeyboardBuilder.build(buttons, current_menu="admin")
        }
