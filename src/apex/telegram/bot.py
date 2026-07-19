
from __future__ import annotations
import asyncio, logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .core.session import SessionManager
from .core.permissions import PermissionManager, Role
from .core.router import CallbackRouter, MessageRouter
from .core.navigation import NavigationManager
from .services.audit_service import AuditService
from .services.notification_service import NotificationService
from .utils.keyboard_builder import KeyboardBuilder
from .utils.message_builder import MessageBuilder

log = logging.getLogger(__name__)

class TelegramBot:
    """Enterprise Telegram Control Center - Main Bot per blueprint
    
    Architecture: Telegram is Presentation Layer only
    All business logic in Application/Domain
    """
    
    def __init__(self, token: str = "", app=None, owner_ids: List[int] = None, admin_ids: List[int] = None):
        self.token = token
        self.app = app
        self.session_manager = SessionManager()
        self.permission_manager = PermissionManager(owner_ids=owner_ids, admin_ids=admin_ids)
        self.callback_router = CallbackRouter()
        self.message_router = MessageRouter()
        self.navigation_manager = NavigationManager()
        self.audit_service = AuditService()
        self.notification_service = NotificationService()
        
        # Controllers - Lazy init via app
        self.backtest_controller = None
        self.optimization_controller = None
        self.trading_controller = None
        self.portfolio_controller = None
        self.admin_controller = None
        
        self._init_controllers()
        self._register_routes()
        
        self.bot_instance = None  # python-telegram-bot Bot
        self.application = None  # PTB Application
    
    def _init_controllers(self):
        try:
            from .controllers.backtest_controller import BacktestController
            from .controllers.optimization_controller import OptimizationController
            from .controllers.trading_controller import TradingController
            from .controllers.portfolio_controller import PortfolioController
            from .controllers.admin_controller import AdminController
            
            backtest_engine = getattr(self.app, 'backtest_engine', None) if self.app else None
            portfolio_engine = getattr(self.app, 'portfolio_engine', None) if self.app else None
            execution_engine = getattr(self.app, 'execution_engine', None) if self.app else None
            health_monitor = getattr(self.app, 'health_monitor', None) if self.app else None
            
            self.backtest_controller = BacktestController(backtest_engine=backtest_engine, app=self.app)
            self.optimization_controller = OptimizationController(app=self.app)
            self.trading_controller = TradingController(app=self.app, execution_engine=execution_engine, portfolio_engine=portfolio_engine)
            self.portfolio_controller = PortfolioController(portfolio_engine=portfolio_engine, app=self.app)
            self.admin_controller = AdminController(app=self.app, health_monitor=health_monitor)
        except Exception as e:
            log.warning(f"Controllers init deferred: {e}")
    
    def _register_routes(self):
        # Main routes
        self.callback_router.register("main", self.handle_main)
        self.callback_router.register("nav.back", self.handle_back)
        
        # Backtest
        self.callback_router.register("backtest.menu", self.handle_backtest_menu)
        self.callback_router.register("backtest.symbol.*", self.handle_backtest_symbol)
        self.callback_router.register("backtest.tf.*", self.handle_backtest_timeframe)
        self.callback_router.register("backtest.run.*", self.handle_backtest_run)
        
        # Trading
        self.callback_router.register("trading.menu", self.handle_trading_menu)
        self.callback_router.register("trading.paper.menu", self.handle_paper_menu)
        self.callback_router.register("trading.live.warning", self.handle_live_warning)
        self.callback_router.register("trading.live.menu", self.handle_live_menu)
        self.callback_router.register("trading.live.positions", self.handle_live_positions)
        self.callback_router.register("trading.live.emergency", self.handle_emergency_menu)
        
        # Optimization
        self.callback_router.register("optimization.menu", self.handle_optimization_menu)
        self.callback_router.register("optimization.run.menu", self.handle_optimization_symbol_menu)
        self.callback_router.register("optimization.symbol.*", self.handle_optimization_symbol)
        self.callback_router.register("optimization.tf.*", self.handle_optimization_timeframe)
        self.callback_router.register("optimization.type.*", self.handle_optimization_type)
        self.callback_router.register("optimization.trials.*", self.handle_optimization_trials)
        self.callback_router.register("optimization.start.*", self.handle_optimization_start)
        self.callback_router.register("optimization.jobs", self.handle_optimization_jobs)
        self.callback_router.register("optimization.versions", self.handle_optimization_versions)
        
        # Portfolio
        self.callback_router.register("portfolio.menu", self.handle_portfolio_menu)
        self.callback_router.register("portfolio.summary", self.handle_portfolio_summary)
        self.callback_router.register("portfolio.positions", self.handle_portfolio_positions)
        
        # Reports
        self.callback_router.register("reports.menu", self.handle_reports_menu)
        
        # Admin
        self.callback_router.register("admin.menu", self.handle_admin_menu)
        self.callback_router.register("admin.health", self.handle_admin_health)
        
        # Status & Help
        self.callback_router.register("status.menu", self.handle_status)
        self.callback_router.register("health.menu", self.handle_admin_health)
        self.callback_router.register("help.menu", self.handle_help)
    
    async def handle_main(self, session, params):
        is_admin = self.permission_manager.is_admin(session.user_id)
        is_owner = self.permission_manager.is_owner(session.user_id)
        from .menus.main import MainMenu
        return {
            "message": MainMenu.get_message(is_admin=is_admin, role=session.role),
            "keyboard": MainMenu.get_keyboard(is_admin=is_admin, is_owner=is_owner),
            "next_state": "main"
        }
    
    async def handle_back(self, session, params):
        prev = session.go_back()
        # Route to previous menu handler
        return await self.handle_main(session, params)
    
    async def handle_backtest_menu(self, session, params):
        from .menus.backtest import BacktestMenu
        if not self.permission_manager.has_permission(session.user_id, "backtest.view"):
            return {"message": MessageBuilder.permission_denied("Analyst"), "keyboard": KeyboardBuilder.main_menu()}
        result = BacktestMenu.symbol_menu()
        result["next_state"] = "backtest_symbol"
        return result
    
    async def handle_backtest_symbol(self, session, params):
        symbol = params.get('value') or params.get('raw','').split('.')[-1]
        session.selected_symbol = symbol
        session.touch()
        from .menus.backtest import BacktestMenu
        result = BacktestMenu.timeframe_menu(symbol)
        result["next_state"] = "backtest_timeframe"
        return result
    
    async def handle_backtest_timeframe(self, session, params):
        raw = params.get('raw','')
        parts = raw.split('.')
        symbol = parts[2] if len(parts) > 2 else session.selected_symbol
        timeframe = parts[3] if len(parts) > 3 else parts[-1]
        session.selected_symbol = symbol
        session.selected_timeframe = timeframe
        session.touch()
        from .menus.backtest import BacktestMenu
        result = BacktestMenu.confirm_menu(symbol, timeframe)
        result["next_state"] = "backtest_confirm"
        return result
    
    async def handle_backtest_run(self, session, params):
        raw = params.get('raw','')
        parts = raw.split('.')
        symbol = parts[2] if len(parts) > 2 else session.selected_symbol
        timeframe = parts[3] if len(parts) > 3 else session.selected_timeframe
        
        # Audit
        self.audit_service.log(session.user_id, session.username, session.role, "backtest.run", {"symbol": symbol, "timeframe": timeframe}, chat_id=session.chat_id)
        
        # Run backtest
        if self.backtest_controller:
            result = await self.backtest_controller.run_backtest(f"{symbol}-SWAP-USDT", timeframe, session.user_id)
            from .menus.backtest import BacktestMenu
            menu_result = BacktestMenu.result_menu(symbol, timeframe, result)
            menu_result["next_state"] = "backtest_result"
            return menu_result
        
        return {"message": f"✅ Backtest started for {symbol} {timeframe} (mock)", "next_state": "backtest_running"}
    
    async def handle_trading_menu(self, session, params):
        from .menus.trading import TradingMenu
        return {**TradingMenu.main_menu(), "next_state": "trading"}
    
    async def handle_paper_menu(self, session, params):
        from .menus.trading import TradingMenu
        return {**TradingMenu.paper_menu(), "next_state": "trading_paper"}
    
    async def handle_live_warning(self, session, params):
        if not self.permission_manager.has_permission(session.user_id, "trading.live.view"):
            return {"message": MessageBuilder.permission_denied("Admin")}
        from .menus.trading import TradingMenu
        return {**TradingMenu.live_warning(), "next_state": "trading_live_warning"}
    
    async def handle_live_menu(self, session, params):
        if not self.permission_manager.has_permission(session.user_id, "trading.live.start"):
            return {"message": MessageBuilder.permission_denied("Admin")}
        from .menus.trading import TradingMenu
        return {**TradingMenu.live_menu(), "next_state": "trading_live"}
    
    async def handle_live_positions(self, session, params):
        if self.trading_controller:
            positions = self.trading_controller.get_positions()
            from .formatters.portfolio_formatter import PortfolioFormatter
            msg = PortfolioFormatter.format_positions(positions)
            return {"message": msg, "next_state": "trading_live_positions"}
        return {"message": "📈 No positions (mock)", "next_state": "trading_live_positions"}
    
    async def handle_emergency_menu(self, session, params):
        if not self.permission_manager.is_admin(session.user_id):
            return {"message": MessageBuilder.permission_denied("Admin")}
        from .menus.trading import TradingMenu
        return {**TradingMenu.emergency_menu(), "next_state": "trading_live_emergency"}
    
    async def handle_optimization_menu(self, session, params):
        if not self.permission_manager.has_permission(session.user_id, "optimization.view"):
            return {"message": MessageBuilder.permission_denied("Analyst")}
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.main_menu(), "next_state": "optimization"}
    
    async def handle_optimization_symbol_menu(self, session, params):
        if not self.permission_manager.has_permission(session.user_id, "optimization.run"):
            return {"message": MessageBuilder.permission_denied("Admin")}
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.symbol_menu(), "next_state": "optimization_symbol"}
    
    async def handle_optimization_symbol(self, session, params):
        symbol = params.get('value') or params.get('raw','').split('.')[-1]
        session.selected_symbol = symbol
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.timeframe_menu(symbol), "next_state": "optimization_timeframe"}
    
    async def handle_optimization_timeframe(self, session, params):
        raw = params.get('raw','')
        parts = raw.split('.')
        symbol = parts[2] if len(parts) > 2 else session.selected_symbol
        timeframe = parts[3] if len(parts) > 3 else parts[-1]
        session.selected_symbol = symbol
        session.selected_timeframe = timeframe
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.type_menu(symbol, timeframe), "next_state": "optimization_type"}
    
    async def handle_optimization_type(self, session, params):
        opt_type = params.get('value') or params.get('raw','').split('.')[-1]
        session.selected_optimizer = opt_type
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.trials_menu(session.selected_symbol, session.selected_timeframe, opt_type), "next_state": "optimization_trials"}
    
    async def handle_optimization_trials(self, session, params):
        trials = int(params.get('value') or params.get('raw','').split('.')[-1] or 100)
        session.temporary_data['trials'] = trials
        from .menus.optimization import OptimizationMenu
        return {**OptimizationMenu.confirm_menu(session.selected_symbol, session.selected_timeframe, session.selected_optimizer, trials), "next_state": "optimization_confirm"}
    
    async def handle_optimization_start(self, session, params):
        raw = params.get('raw','')
        parts = raw.split('.')
        symbol = parts[2] if len(parts) > 2 else session.selected_symbol
        timeframe = parts[3] if len(parts) > 3 else session.selected_timeframe
        opt_type = parts[4] if len(parts) > 4 else session.selected_optimizer
        trials = int(parts[5]) if len(parts) > 5 else session.temporary_data.get('trials', 50)
        
        self.audit_service.log(session.user_id, session.username, session.role, "optimization.run", {"symbol": symbol, "timeframe": timeframe, "type": opt_type, "trials": trials}, chat_id=session.chat_id)
        
        if self.optimization_controller:
            result = await self.optimization_controller.run_optimization(f"{symbol}-SWAP-USDT", timeframe, opt_type, trials, session.user_id)
            package = result.get('package')
            if package:
                from .formatters.optimization_formatter import OptimizationFormatter
                msg = OptimizationFormatter.format_package(package)
                return {"message": msg, "next_state": "optimization"}
        
        return {"message": f"🚀 Optimization started for {symbol} {timeframe} {opt_type} {trials} trials\nCheck /opt_status", "next_state": "optimization"}
    
    async def handle_optimization_jobs(self, session, params):
        if self.optimization_controller:
            status = self.optimization_controller.get_queue_status()
            from ..optimization.reports.telegram_formatter import TelegramOptimizationFormatter
            formatter = TelegramOptimizationFormatter()
            msg = formatter.format_queue_status(status)
            return {"message": msg, "next_state": "optimization_jobs"}
        return {"message": "📋 No jobs (mock)", "next_state": "optimization_jobs"}
    
    async def handle_optimization_versions(self, session, params):
        if self.optimization_controller:
            versions = self.optimization_controller.list_versions(f"{session.selected_symbol}-SWAP-USDT", session.selected_timeframe, session.selected_optimizer)
            from .formatters.optimization_formatter import OptimizationFormatter
            msg = OptimizationFormatter.format_version_list(versions, session.selected_symbol, session.selected_timeframe)
            return {"message": msg, "next_state": "optimization_versions"}
        return {"message": "📚 No versions", "next_state": "optimization_versions"}
    
    async def handle_portfolio_menu(self, session, params):
        from .menus.portfolio import PortfolioMenu
        return {**PortfolioMenu.main_menu(), "next_state": "portfolio"}
    
    async def handle_portfolio_summary(self, session, params):
        if self.portfolio_controller:
            summary = self.portfolio_controller.get_summary()
            from .formatters.portfolio_formatter import PortfolioFormatter
            msg = PortfolioFormatter.format_summary(summary)
            return {"message": msg, "next_state": "portfolio_summary"}
        return {"message": "💼 Portfolio summary (mock)", "next_state": "portfolio_summary"}
    
    async def handle_portfolio_positions(self, session, params):
        if self.portfolio_controller:
            positions = self.portfolio_controller.get_positions()
            from .formatters.portfolio_formatter import PortfolioFormatter
            msg = PortfolioFormatter.format_positions(positions)
            return {"message": msg, "next_state": "portfolio_positions"}
        return {"message": "📈 Positions (mock)", "next_state": "portfolio_positions"}
    
    async def handle_reports_menu(self, session, params):
        from .menus.reports import ReportsMenu
        return {**ReportsMenu.main_menu(), "next_state": "reports"}
    
    async def handle_admin_menu(self, session, params):
        if not self.permission_manager.is_admin(session.user_id):
            return {"message": MessageBuilder.permission_denied("Admin")}
        from .menus.admin import AdminMenu
        is_owner = self.permission_manager.is_owner(session.user_id)
        return {**AdminMenu.main_menu(is_owner=is_owner), "next_state": "admin"}
    
    async def handle_admin_health(self, session, params):
        if not self.permission_manager.is_admin(session.user_id):
            return {"message": MessageBuilder.permission_denied("Admin")}
        if self.admin_controller:
            health = self.admin_controller.get_health()
            msg = f"""❤️ **System Health**

CPU: {health.get('cpu',0):.1f}%
Memory: {health.get('memory',0):.1f}%
Disk: {health.get('disk',0):.1f}%
Status: {health.get('status','unknown')}

Timestamp: {health.get('timestamp','')}
"""
            return {"message": msg, "next_state": "admin_health"}
        return {"message": "❤️ Health: OK (mock)", "next_state": "admin_health"}
    
    async def handle_status(self, session, params):
        status = {
            "engine": "Running",
            "ws": "Connected",
            "exchange": "Online",
            "paper": "Stopped",
            "live": "Stopped",
            "positions": 1,
            "opt_queue": 0,
            "opt_running": 0,
            "health": "100%"
        }
        return {"message": MessageBuilder.status_message(status), "next_state": "status"}
    
    async def handle_help(self, session, params):
        msg = """❓ **APEX Help**

**Main Menu:**
📊 Backtest - Full history backtest
📈 Trading - Paper & Live trading
🧠 Optimization - Signal & Risk optimization
📁 Reports - Export & analysis
💼 Portfolio - Positions & PnL
⚙ Settings - Notifications, risk
❤️ Health - System status
🛡 Admin - Admin panel (admin only)

**Navigation:**
⬅ Back - Previous menu
🏠 Home - Main menu
🔄 Refresh - Refresh current view

**Optimization:**
Isolation enforced: Never Mix Coins/Timeframes
All artifacts versioned & audited

**Support:**
Contact owner for role upgrade
"""
        return {"message": msg, "next_state": "help"}
    
    # PTB Integration
    async def on_message(self, update, context):
        """Handle incoming message"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            text = update.message.text if update.message else ""
            
            session = self.session_manager.get_or_create(user.id, chat.id, user.username or "", self.permission_manager.get_role(user.id).value)
            session.username = user.username or ""
            
            # Check if command
            if text.startswith("/"):
                cmd_result = self.message_router.route_command(text)
                if cmd_result:
                    handler, params = cmd_result
                    result = await handler(session, params)
                    await self.send_result(update, result, session)
                    return
                # Default commands
                if text.startswith("/start") or text.startswith("/menu"):
                    result = await self.handle_main(session, {})
                    await self.send_result(update, result, session)
                    return
            
            # Default to main
            result = await self.handle_main(session, {})
            await self.send_result(update, result, session)
            
        except Exception as e:
            log.error(f"on_message error: {e}", exc_info=True)
            try:
                await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
            except:
                pass
    
    async def on_callback(self, update, context):
        """Handle callback query"""
        try:
            query = update.callback_query
            await query.answer()
            
            user = update.effective_user
            chat = update.effective_chat
            data = query.data
            
            session = self.session_manager.get_or_create(user.id, chat.id, user.username or "", self.permission_manager.get_role(user.id).value)
            
            # Route callback
            route_result = self.callback_router.route(data)
            if not route_result:
                await query.edit_message_text(f"❌ Unknown action: {data}\nUse 🏠 Home")
                return
            
            handler, params = route_result
            result = await handler(session, params)
            
            # Update session
            if result and "next_state" in result:
                session.set_menu(result["next_state"])
                self.session_manager.update(session)
            
            await self.send_callback_result(query, result, session)
            
            # Audit
            self.audit_service.log(user.id, user.username or "", session.role, f"callback:{data}", params, chat_id=chat.id, old_state=session.previous_menu, new_state=session.current_menu)
            
        except Exception as e:
            log.error(f"on_callback error: {e}", exc_info=True)
            try:
                await update.callback_query.edit_message_text(f"❌ Error: {str(e)[:200]}\nUse 🏠 Home")
            except:
                pass
    
    async def send_result(self, update, result: Dict[str, Any], session):
        if not result:
            return
        message = result.get("message", "No message")
        keyboard = result.get("keyboard")
        try:
            if keyboard:
                await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
            # Save message id
            if hasattr(update.message, 'message_id'):
                session.last_message_id = update.message.message_id
        except Exception as e:
            # Fallback without markdown
            try:
                if keyboard:
                    await update.message.reply_text(message[:4000], reply_markup=keyboard)
                else:
                    await update.message.reply_text(message[:4000])
            except Exception as e2:
                log.error(f"Send result failed: {e2}")
    
    async def send_callback_result(self, query, result: Dict[str, Any], session):
        if not result:
            return
        message = result.get("message", "No message")
        keyboard = result.get("keyboard")
        try:
            if keyboard:
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
            else:
                await query.edit_message_text(message, parse_mode='Markdown')
        except Exception as e:
            # Try without markdown or as new message
            try:
                if keyboard:
                    await query.edit_message_text(message[:4000], reply_markup=keyboard)
                else:
                    await query.edit_message_text(message[:4000])
            except Exception as e2:
                try:
                    # Send as new message
                    await query.message.reply_text(message[:4000], reply_markup=keyboard, parse_mode='Markdown' if keyboard else None)
                except:
                    log.error(f"Send callback result failed: {e2}")
    
    def run(self, token: str = None):
        """Run bot with python-telegram-bot"""
        try:
            from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
            
            token = token or self.token
            if not token:
                log.error("No telegram token provided")
                return
            
            app = Application.builder().token(token).build()
            self.application = app
            self.bot_instance = app.bot
            self.notification_service.bot = app.bot
            
            app.add_handler(CommandHandler("start", self.on_message))
            app.add_handler(CommandHandler("menu", self.on_message))
            app.add_handler(CommandHandler("status", self.on_message))
            app.add_handler(CallbackQueryHandler(self.on_callback))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
            
            log.info("🤖 Telegram Bot starting...")
            app.run_polling()
        except ImportError:
            log.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
        except Exception as e:
            log.error(f"Bot run failed: {e}", exc_info=True)
