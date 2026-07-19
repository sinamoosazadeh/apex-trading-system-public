"""Application Bootstrap - Wires all components and manages lifecycle."""
from __future__ import annotations
import asyncio
import signal
import logging
import os
from collections import defaultdict

from ..core.events import EventBus, Event
from ..core.types.enums import EventType, OrderStatus
from ..domain.market import MarketBar, Tick
from ..domain.trading import Position
from ..infrastructure.exchanges.toobit_ws import ToobitWebSocketClient
from ..infrastructure.exchanges.toobit_adapter import ToobitAdapter
from ..engines.probability_engine import ProbabilityEngine
from ..engines.governance import GovernanceEngine, GovernancePolicy
from ..engines.decision_engine import DecisionEngine
from ..engines.risk_engine import RiskEngine
from ..engines.portfolio_engine import PortfolioEngine
from ..engines.execution_engine import ExecutionEngine
from ..engines.digital_twin import DigitalTwin
from ..engines.meta_intelligence import MetaIntelligenceEngine
from ..engines.kernel import CentralDecisionKernel
from ..features.feature_store import FeatureStore
from ..research.knowledge_base import KnowledgeBase
from ..research.research_engine import ResearchEngine
from ..optimizers.meta_optimizer import MetaOptimizer
from ..monitoring.structured_logger import StructuredLogger
from ..monitoring.metrics_engine import MetricsEngine
from ..monitoring.health_monitor import HealthMonitor
from ..interfaces.telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = StructuredLogger("APEX.Application")

class Application:
    def __init__(self, api_key: str, api_secret: str, symbols: list[str], initial_capital: float = 10000.0) -> None:
        self._running = False
        self.mode = "PAPER"
        self.active_intime_symbol = None
        self.active_intime_tf = None  # Added to track active TF
        
        self.is_backtesting = False
        self.backtest_signals = []
        
        self.tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        self.event_bus = EventBus()
        self.metrics = MetricsEngine()
        self.health = HealthMonitor()
        
        self.feature_store = FeatureStore()
        self.probability_engine = ProbabilityEngine()
        self.knowledge_base = KnowledgeBase()
        self.research_engine = ResearchEngine(self.knowledge_base, self.probability_engine)
        self.portfolio_engine = PortfolioEngine(initial_capital=initial_capital)
        self.governance = GovernanceEngine(GovernancePolicy())
        self.decision_engine = DecisionEngine(self.governance)
        self.risk_engine = RiskEngine()
        
        self.toobit_adapter = ToobitAdapter(api_key, api_secret)
        self.execution_engine = ExecutionEngine(self.toobit_adapter)
        self.digital_twin = DigitalTwin(initial_capital)
        self.meta_engine = MetaIntelligenceEngine(self.health)
        
        self.kernel = CentralDecisionKernel(
            feature_store=self.feature_store,
            prob_engine=self.probability_engine,
            decision_engine=self.decision_engine,
            risk_engine=self.risk_engine,
            portfolio_engine=self.portfolio_engine,
            execution_engine=self.execution_engine,
            research_engine=self.research_engine,
            digital_twin=self.digital_twin,
            meta_engine=self.meta_engine,
            health_monitor=self.health
        )
        self.kernel.app = self
        
        self.ws_client = ToobitWebSocketClient(self.event_bus, [])
        
        self.tg_bot = None
        if self.tg_token and self.tg_chat_id:
            try:
                self.tg_bot = TelegramBot(self)
            except Exception as e:
                log.error(f"Failed to init Telegram Bot: {e}")
                
        for mod in ["Application", "CDK", "ProbabilityEngine", "ExecutionEngine", "WebSocket"]:
            self.health.register_module(mod)

    async def initialize(self) -> None:
        log.info("Initializing Institutional APEX Trading System...")
        log.info("Waiting for Telegram commands. Send /start to your bot.")
        
        self.event_bus.subscribe(EventType.NEW_CANDLE, self._on_new_candle)
        self.event_bus.subscribe(EventType.NEW_TICK, self._on_new_tick)
        
        if self.tg_bot:
            self.tg_task = asyncio.create_task(self.tg_bot.run())
            self.tg_task.add_done_callback(self._on_tg_done)
            
        self.optimizer = MetaOptimizer(self)
        self.optimizer_task = asyncio.create_task(self.optimizer.run())
            
    def _on_tg_done(self, task):
        try:
            task.result()
        except Exception as e:
            log.error(f"Telegram Bot task crashed: {e}", exc_info=True)

    async def send_telegram_signal(self, msg: str) -> None:
        if self.is_backtesting:
            self.backtest_signals.append(msg)
        elif self.tg_bot:
            await self.tg_bot.send_signal(msg)

    async def _on_new_tick(self, event: Event) -> None:
        self.health.heartbeat("WebSocket")
        tick_data = event.payload.get("tick")
        if not tick_data: return
        
        tick = Tick(**tick_data)
        self.kernel.process_tick(tick)
        self.portfolio_engine.update_positions({tick.symbol: tick.price})
        
        for pos in list(self.portfolio_engine.open_positions.values()):
            if pos.symbol != tick.symbol or pos.status != "OPEN": continue
            hit_sl = (pos.direction == "LONG" and tick.price <= pos.stop_loss) or \
                     (pos.direction == "SHORT" and tick.price >= pos.stop_loss)
            hit_tp = (pos.direction == "LONG" and tick.price >= pos.take_profit) or \
                     (pos.direction == "SHORT" and tick.price <= pos.take_profit)
            if hit_sl or hit_tp:
                await self.kernel.close_position_workflow(pos, tick.price, "SL/TP Hit")

    async def _on_new_candle(self, event: Event) -> None:
        bar_data = event.payload.get("bar")
        if not bar_data: return
        
        bar = MarketBar(**bar_data)
        if self.active_intime_symbol == bar.symbol:
            await self.kernel.process_bar(bar, ref_bar=None)

    async def run(self) -> None:
        await self.initialize()
        self._running = True
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            
        ws_task = asyncio.create_task(self.ws_client.connect())
        log.info("APEX System is LIVE. Background Optimizer is active.")
        
        try:
            while self._running:
                await asyncio.sleep(10.0)
                self.health.heartbeat("Application")
        except asyncio.CancelledError:
            pass
        finally:
            if hasattr(self, 'optimizer_task'):
                self.optimizer_task.cancel()
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        log.info("Shutdown signal received...")
        self._running = False
        if hasattr(self, 'optimizer'):
            await self.optimizer.stop()
            
        for pos in list(self.portfolio_engine.open_positions.values()):
            if pos.status == "OPEN":
                await self.kernel.close_position_workflow(pos, pos.current_price, "System Shutdown")
        await self.ws_client.disconnect()
        await self.toobit_adapter.client.close()
        log.info("System shutdown complete.")
