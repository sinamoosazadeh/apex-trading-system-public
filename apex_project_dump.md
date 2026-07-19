
### File: `src/apex/__init__.py`
```python

```

### File: `src/apex/application/__init__.py`
```python

```

### File: `src/apex/application/bootstrap.py`
```python
"""Application Bootstrap - Full Institutional Integration."""
from __future__ import annotations

import asyncio
import signal
import logging
from collections import defaultdict

from ..core.events import EventBus, Event
from ..core.types.enums import EventType, OrderStatus
from ..domain.market import MarketBar
from ..domain.trading import Position
from ..domain.knowledge import Experience
from ..infrastructure.exchanges.toobit_ws import ToobitWebSocketClient
from ..infrastructure.exchanges.toobit_adapter import ToobitAdapter
from ..engines.probability_engine import ProbabilityEngine
from ..engines.governance import GovernanceEngine, GovernancePolicy
from ..engines.decision_engine import DecisionEngine
from ..engines.risk_engine import RiskEngine
from ..engines.portfolio_engine import PortfolioEngine
from ..engines.execution_engine import ExecutionEngine
from ..features.feature_store import FeatureStore
from ..features.primitives import PrimitiveFeatures
from ..features.structure import update_structure, StructureState, detect_fvgs, detect_order_blocks
from ..features.regime_engine import RegimeEngine
from ..research.knowledge_base import KnowledgeBase
from ..research.research_engine import ResearchEngine
from ..monitoring.structured_logger import StructuredLogger
from ..monitoring.metrics_engine import MetricsEngine
from ..monitoring.health_monitor import HealthMonitor

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = StructuredLogger("APEX.Application")

class Application:
    def __init__(self, api_key: str, api_secret: str, symbols: list[str], initial_capital: float = 10000.0) -> None:
        self.symbols = symbols
        self._running = False
        
        self.event_bus = EventBus()
        self.metrics = MetricsEngine()
        self.health = HealthMonitor()
        
        self.feature_store = FeatureStore()
        self.primitive_features = PrimitiveFeatures(self.feature_store)
        self.regime_engine = RegimeEngine()
        self.bars_history: dict[str, list[MarketBar]] = defaultdict(list)
        self.last_processed_ts: dict[str, float] = defaultdict(float)
        self._structure_state = StructureState()
        
        self.probability_engine = ProbabilityEngine()
        self.knowledge_base = KnowledgeBase()
        self.research_engine = ResearchEngine(self.knowledge_base, self.probability_engine)
        self.portfolio_engine = PortfolioEngine(initial_capital=initial_capital)
        self.governance = GovernanceEngine(GovernancePolicy())
        self.decision_engine = DecisionEngine(self.governance)
        self.risk_engine = RiskEngine()
        
        self.toobit_adapter = ToobitAdapter(api_key, api_secret)
        self.execution_engine = ExecutionEngine(self.toobit_adapter)
        self.ws_client = ToobitWebSocketClient(self.event_bus, symbols)
        
        for mod in ["Application", "ProbabilityEngine", "ExecutionEngine", "WebSocket"]:
            self.health.register_module(mod)

    async def initialize(self) -> None:
        log.info("Initializing Institutional APEX Trading System...")
        self.event_bus.subscribe(EventType.NEW_CANDLE, self._on_new_candle)
        self.event_bus.subscribe(EventType.NEW_TICK, self._on_new_tick)
        log.info("Waiting for WebSocket data to warm up (requires ~50 minutes for 50 bars)...")

    async def _on_new_tick(self, event: Event) -> None:
        self.health.heartbeat("WebSocket")
        tick_data = event.payload.get("tick")
        if not tick_data: return
        
        symbol = tick_data["symbol"]
        current_price = tick_data["price"]
        self.portfolio_engine.update_positions({symbol: current_price})
        
        for pos in list(self.portfolio_engine.open_positions.values()):
            if pos.symbol != symbol or pos.status != "OPEN": continue
            hit_sl = (pos.direction == "LONG" and current_price <= pos.stop_loss) or \
                     (pos.direction == "SHORT" and current_price >= pos.stop_loss)
            hit_tp = (pos.direction == "LONG" and current_price >= pos.take_profit) or \
                     (pos.direction == "SHORT" and current_price <= pos.take_profit)
            if hit_sl or hit_tp:
                await self._close_position(pos, current_price, "SL/TP Hit")

    async def _on_new_candle(self, event: Event) -> None:
        bar_data = event.payload.get("bar")
        if not bar_data: return
        
        bar = MarketBar(**bar_data)
        history = self.bars_history[bar.symbol]
        
        if self.last_processed_ts[bar.symbol] == bar.timestamp:
            if history and history[-1].timestamp == bar.timestamp:
                history[-1] = bar
            return
            
        self.last_processed_ts[bar.symbol] = bar.timestamp
        history.append(bar)
        
        if len(history) > 50:
            history.pop(0)
            
        if len(history) < 20:
            log.info(f"Collecting data for {bar.symbol}: {len(history)}/20 bars collected.")
            return
            
        # 1. Primitive Features
        atr_feat = self.primitive_features.calculate_atr(history, 14, bar.symbol, bar.timeframe)
        rsi_feat = self.primitive_features.calculate_rsi(history, 14, bar.symbol, bar.timeframe)
        
        # 2. Regime Detection
        regime = self.regime_engine.detect_regime(history)
        
        # 3. Market Structure (ICT/SMC)
        highs = [b.high for b in history]
        lows = [b.low for b in history]
        closes = [b.close for b in history]
        self._structure_state = update_structure(self._structure_state, highs, lows, closes, atr_feat.value)
        
        # 4. OB & FVG Detection
        obs = detect_order_blocks(history, self._structure_state.bos_up, self._structure_state.bos_dn)
        bull_fvg, bear_fvg = detect_fvgs(history)
        
        # 5. Build Evidence Vector based on Institutional Logic
        ev_long = {}
        ev_short = {}
        
        # Trend & Momentum
        ev_long["momentum"] = 1.0 if rsi_feat.value < 40 else 0.2
        ev_short["momentum"] = 1.0 if rsi_feat.value > 60 else 0.2
        
        # Structure
        ev_long["structure"] = 1.0 if self._structure_state.bos_up or self._structure_state.choch_up else 0.3
        ev_short["structure"] = 1.0 if self._structure_state.bos_dn or self._structure_state.choch_dn else 0.3
        
        # Imbalances (FVG)
        ev_long["fvg"] = 0.8 if bull_fvg else 0.2
        ev_short["fvg"] = 0.8 if bear_fvg else 0.2
        
        # Order Blocks
        ev_long["ob"] = 0.8 if any(ob.top > bar.close for ob in obs) else 0.2
        ev_short["ob"] = 0.8 if any(ob.bot < bar.close for ob in obs) else 0.2
        
        weights = {"momentum": 0.2, "structure": 0.4, "fvg": 0.2, "ob": 0.2}
        
        # 6. Probability Engine
        prob_report = self.probability_engine.compute_probability(
            ev_long, ev_short, weights, trend_confidence=regime.trend_confidence
        )
        
        # 7. Decision Engine
        portfolio_state = self.portfolio_engine.get_state()
        decision = self.decision_engine.evaluate(
            prob_report, portfolio_state, 
            contributors_long=len([v for v in ev_long.values() if v > 0.5]), 
            contributors_short=len([v for v in ev_short.values() if v > 0.5])
        )
        
        # 8. Risk & Execution
        if decision.decision_type == "TRADE":
            log.info(f"Institutional Trade Decision: {decision.direction} {bar.symbol}", confidence=decision.confidence, regime=regime.trend_class)
            
            # Pass structural levels to Risk Engine for Hybrid SL
            struct_low = min(b.low for b in history[-5:]) if history else None
            struct_high = max(b.high for b in history[-5:]) if history else None
            
            blueprint = self.risk_engine.create_blueprint(
                decision, portfolio_state, prob_report, bar.close, atr_feat.value,
                structure_low=struct_low, structure_high=struct_high
            )
            
            if blueprint:
                order_response = await self.execution_engine.execute_blueprint(blueprint)
                if order_response.get("status") in ["NEW", "PARTIALLY_FILLED", "FILLED"]:
                    position = Position(
                        position_id=order_response.get("orderId", "unknown"),
                        blueprint_id=blueprint.decision_id, symbol=bar.symbol, exchange="toobit",
                        direction=decision.direction, entry_price=bar.close, quantity=blueprint.position_size,
                        stop_loss=blueprint.stop_loss, take_profit=blueprint.take_profit
                    )
                    self.portfolio_engine.add_position(position)
                    
                    exp = Experience(
                        trade_id=position.position_id, symbol=bar.symbol, setup_name="Institutional_Integration",
                        direction=decision.direction, win=False, r_multiple=0.0, 
                        probability_at_entry=prob_report.probability_long if decision.direction == "LONG" else prob_report.probability_short,
                        uncertainty_at_entry=prob_report.uncertainty, regime=regime.trend_class
                    )
                    self.research_engine.record_trade_context(position.position_id, exp)
                    log.info(f"Position opened: {position.position_id}")

    async def _close_position(self, position: Position, exit_price: float, reason: str) -> None:
        log.info(f"Closing position {position.position_id} due to {reason}")
        trade = self.portfolio_engine.close_position(position.position_id, exit_price)
        if trade:
            self.research_engine.process_closed_trade(trade)
            log.info(f"Trade closed. PnL: {trade.pnl:.2f} R: {trade.r_multiple:.2f}")

    async def run(self) -> None:
        await self.initialize()
        self._running = True
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            
        ws_task = asyncio.create_task(self.ws_client.connect())
        log.info("APEX System is LIVE and listening to markets.")
        
        try:
            while self._running:
                await asyncio.sleep(10.0)
                self.health.heartbeat("Application")
        except asyncio.CancelledError:
            pass
        finally:
            await ws_task.cancel()

    async def shutdown(self) -> None:
        log.info("Shutdown signal received...")
        self._running = False
        for pos in list(self.portfolio_engine.open_positions.values()):
            if pos.status == "OPEN":
                await self._close_position(pos, pos.current_price, "System Shutdown")
        await self.ws_client.disconnect()
        await self.toobit_adapter.client.close()
        log.info("System shutdown complete.")

```

### File: `src/apex/application/cli.py`
```python
"""Command-line interface for APEX."""
from __future__ import annotations

import asyncio
import argparse
import os
from .bootstrap import Application

def main() -> None:
    """Entry point for the APEX CLI."""
    parser = argparse.ArgumentParser(description="APEX Trading Intelligence Platform")
    parser.add_argument("--api-key", default=os.getenv("TOOBIT_API_KEY"), help="Toobit API Key")
    parser.add_argument("--api-secret", default=os.getenv("TOOBIT_API_SECRET"), help="Toobit API Secret")
    parser.add_argument("--symbol", "-s", action="append", help="Trading symbol")
    parser.add_argument("--capital", "-c", type=float, default=10000.0, help="Initial capital (USDT)")
    
    args = parser.parse_args()
    
    # اگر نمادی وارد نشده بود، پیش‌فرض را قرار بده
    symbols = args.symbol if args.symbol else ["BTC-SWAP-USDT"]
    
    if not args.api_key or not args.api_secret:
        print("Error: TOOBIT_API_KEY and TOOBIT_API_SECRET must be provided.")
        return

    app = Application(
        api_key=args.api_key,
        api_secret=args.api_secret,
        symbols=symbols,
        initial_capital=args.capital
    )
    asyncio.run(app.run())

if __name__ == "__main__":
    main()

```

### File: `src/apex/core/__init__.py`
```python

```

### File: `src/apex/core/events.py`
```python
"""Event system - immutable, versioned, traceable."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from collections import defaultdict
import asyncio
import uuid
from datetime import datetime, timezone
from .types.enums import EventType

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def generate_id() -> str:
    return str(uuid.uuid4())

@dataclass(frozen=True)
class Event:
    """Immutable event object."""
    id: str = field(default_factory=generate_id)
    event_type: EventType = EventType.SYSTEM_STARTUP
    timestamp: str = field(default_factory=lambda: utc_now().isoformat())
    source: str = ""
    destination: str = ""
    priority: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    correlation_id: str = ""
    version: str = "1.0.0"

EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    """In-memory async event bus with priority queues."""
    
    def __init__(self, max_history: int = 10000) -> None:
        self._handlers: dict[EventType, list[tuple[int, EventHandler]]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history: int = max_history

    def subscribe(self, event_type: EventType, handler: EventHandler, priority: int = 0) -> None:
        self._handlers[event_type].append((priority, handler))
        self._handlers[event_type].sort(key=lambda x: -x[0])

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        tasks = [handler(event) for _, handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

```

### File: `src/apex/core/interfaces.py`
```python
"""Core interfaces for system abstraction."""
from __future__ import annotations

from typing import Protocol
from ..domain.trading import TradeBlueprint, Position

class IExchangeAdapter(Protocol):
    """Exchange abstraction interface (Book II, 3.5)."""

    async def place_order(self, blueprint: TradeBlueprint) -> dict:
        """Submit a new order to the exchange and return raw response."""
        ...

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order."""
        ...

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Query the status of an order."""
        ...

```

### File: `src/apex/core/types/__init__.py`
```python

```

### File: `src/apex/core/types/enums.py`
```python
"""Enumerations for type-safe business logic."""
from __future__ import annotations

from enum import Enum

class Direction(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0

class OrderStatus(Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class EventType(Enum):
    NEW_CANDLE = "new_candle"
    NEW_TICK = "new_tick"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"

```

### File: `src/apex/core/types/primitives.py`
```python
"""Strong-typed primitive wrappers for type safety."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
from typing import Union

@dataclass(frozen=True)
class Price:
    """Immutable price value object with validation."""
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            try:
                object.__setattr__(self, 'value', Decimal(str(self.value)))
            except InvalidOperation:
                raise ValueError(f"Invalid price value: {self.value}")
        
        if self.value < 0:
            raise ValueError(f"Price cannot be negative: {self.value}")
        if math.isnan(float(self.value)) or math.isinf(float(self.value)):
            raise ValueError(f"Price must be finite: {self.value}")

    def __float__(self) -> float:
        return float(self.value)

    def __add__(self, other: 'Price') -> 'Price':
        return Price(self.value + other.value)

@dataclass(frozen=True)
class Probability:
    """Probability value strictly in [0, 1]."""
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Probability must be in [0, 1], got {self.value}")
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Probability must be finite: {self.value}")

    def __float__(self) -> float:
        return self.value

    def complement(self) -> 'Probability':
        return Probability(1.0 - self.value)

@dataclass(frozen=True)
class Confidence:
    """Confidence score in [0, 1]."""
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confidence must be in [0, 1], got {self.value}")

    def __float__(self) -> float:
        return self.value

```

### File: `src/apex/domain/__init__.py`
```python

```

### File: `src/apex/domain/contracts.py`
```python
"""Standardized contracts and DTOs for engine communication."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class ProbabilityReport:
    """Output contract from Probability Engine. Immutable and validated."""
    probability_long: float = 0.0
    probability_short: float = 0.0
    probability_neutral: float = 0.0
    confidence: float = 0.0
    uncertainty: float = 0.0
    entropy: float = 0.0
    consensus: float = 0.0
    calibration_score: float = 0.0
    expected_value: float = 0.0
    expected_r: float = 0.0
    expected_rr: float = 0.0
    expected_drawdown: float = 0.0
    expected_adverse_excursion: float = 0.0
    expected_favorable_excursion: float = 0.0
    trade_survival_probability: float = 0.0
    expected_holding_time: int = 0
    scenario_distribution: dict[str, float] = field(default_factory=dict)
    feature_attribution: dict[str, float] = field(default_factory=dict)
    evidence_summary: dict[str, float] = field(default_factory=dict)
    regime: str = "neutral"
    decision_readiness_index: float = 0.0
    model_version: str = "2.0.0"
    health_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.probability_long, self.probability_short, self.probability_neutral, 
                    self.confidence, self.uncertainty, self.entropy, self.consensus]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"ProbabilityReport contains NaN or Inf: {val}")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Probability metric out of bounds [0, 1]: {val}")
        
        total_prob = self.probability_long + self.probability_short + self.probability_neutral
        if not math.isclose(total_prob, 1.0, abs_tol=1e-6):
            raise ValueError(f"Probabilities must sum to 1.0, got {total_prob}")

```

### File: `src/apex/domain/knowledge.py`
```python
"""Knowledge and Research domain objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time
import math

@dataclass(frozen=True)
class Experience:
    """Record of a completed trade and its context for learning."""
    trade_id: str
    symbol: str
    setup_name: str
    direction: str
    win: bool
    r_multiple: float
    probability_at_entry: float
    uncertainty_at_entry: float
    regime: str
    feature_vector: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        for val in [self.r_multiple, self.probability_at_entry, self.uncertainty_at_entry]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Experience contains NaN or Inf: {val}")
        if not (0.0 <= self.probability_at_entry <= 1.0):
            raise ValueError("Probability must be in [0, 1]")

@dataclass(frozen=True)
class Knowledge:
    """Extracted pattern or rule from experiences."""
    knowledge_id: str
    category: str  # 'setup_performance', 'regime_edge', 'feature_drift'
    description: str
    confidence: float
    sample_size: int
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Knowledge confidence out of bounds: {self.confidence}")

```

### File: `src/apex/domain/market.py`
```python
"""Market data domain objects with strict validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class Tick:
    """Individual market tick. Immutable and validated."""
    timestamp: float
    price: float
    volume: float
    side: str  # 'buy' or 'sell'
    trade_id: str = ""
    exchange: str = ""
    symbol: str = ""
    receive_time: float = 0.0
    sequence: int = 0
    quality_score: float = 1.0

    def __post_init__(self) -> None:
        if math.isnan(self.price) or math.isinf(self.price):
            raise ValueError(f"Tick price must be finite: {self.price}")
        if self.price <= 0:
            raise ValueError(f"Tick price must be positive: {self.price}")
        if math.isnan(self.volume) or math.isinf(self.volume):
            raise ValueError(f"Tick volume must be finite: {self.volume}")
        if self.volume < 0:
            raise ValueError(f"Tick volume cannot be negative: {self.volume}")
        if self.side not in ('buy', 'sell'):
            raise ValueError(f"Invalid tick side: {self.side}")

@dataclass(frozen=True)
class OrderBookLevel:
    """Single level in order book."""
    price: float
    quantity: float
    orders: int = 0

    def __post_init__(self) -> None:
        if math.isnan(self.price) or math.isinf(self.price):
            raise ValueError("OrderBookLevel price must be finite")
        if math.isnan(self.quantity) or math.isinf(self.quantity):
            raise ValueError("OrderBookLevel quantity must be finite")

@dataclass(frozen=True)
class OrderBook:
    """Order book snapshot. Immutable and validated."""
    timestamp: float
    symbol: str
    bids: tuple[OrderBookLevel, ...] = field(default_factory=tuple)
    asks: tuple[OrderBookLevel, ...] = field(default_factory=tuple)
    exchange: str = ""

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid <= 0:
            return 0.0
        return (self.spread / mid) * 10000.0

    @property
    def bid_volume(self) -> float:
        return sum(level.quantity for level in self.bids[:20])

    @property
    def ask_volume(self) -> float:
        return sum(level.quantity for level in self.asks[:20])

    @property
    def imbalance(self) -> float:
        total = self.bid_volume + self.ask_volume
        if total == 0:
            return 0.0
        return (self.bid_volume - self.ask_volume) / total

@dataclass(frozen=True)
class MarketBar:
    """OHLCV candle bar. Immutable and validated."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    trades: int = 0
    vwap: float = 0.0
    spread: float = 0.0
    funding: float = 0.0
    open_interest: float = 0.0
    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1m"
    quality_score: float = 1.0

    def __post_init__(self) -> None:
        # Numerical Stability Policy
        for val in [self.open, self.high, self.low, self.close, self.volume]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"MarketBar contains NaN or Inf: {self.symbol} {self.timestamp}")
        
        # Market Rule Validation
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) < Low ({self.low}) for {self.symbol}")
        if self.open < 0 or self.close < 0:
            raise ValueError("Price cannot be negative")
        if self.high < max(self.open, self.close):
            raise ValueError(f"High ({self.high}) < Open/Close ({self.open}/{self.close})")
        if self.low > min(self.open, self.close):
            raise ValueError(f"Low ({self.low}) > Open/Close ({self.open}/{self.close})")

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_frac(self) -> float:
        r = self.range
        return self.body / r if r > 0 else 0.0

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def close_location(self) -> float:
        r = self.range
        return (self.close - self.low) / r if r > 0 else 0.5

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def log_return(self) -> float:
        if self.open <= 0:
            return 0.0
        return math.log(self.close / self.open)

```

### File: `src/apex/domain/trading.py`
```python
"""Trading domain objects - Portfolio State, Decisions, Blueprints, Positions, Trades."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math
import time

@dataclass(frozen=True)
class PortfolioState:
    """Portfolio state snapshot for decision making."""
    total_equity: float = 10000.0
    available_capital: float = 10000.0
    total_exposure: float = 0.0
    open_positions_count: int = 0
    risk_budget: float = 3.0
    risk_budget_used: float = 0.0
    portfolio_heat: float = 0.0
    drawdown: float = 0.0
    health_score: float = 1.0

    def __post_init__(self) -> None:
        for val in [self.total_equity, self.available_capital, self.total_exposure, 
                    self.risk_budget, self.risk_budget_used, self.drawdown]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"PortfolioState contains NaN or Inf: {val}")
        if self.total_equity < 0:
            raise ValueError("Total equity cannot be negative")

@dataclass(frozen=True)
class Decision:
    """Final decision contract."""
    decision_type: str
    direction: str
    confidence: float = 0.0
    utility: float = 0.0
    priority: int = 0
    reasoning: tuple[str, ...] = field(default_factory=tuple)
    evidence_summary: dict[str, float] = field(default_factory=dict)
    risk_summary: dict[str, float] = field(default_factory=dict)
    portfolio_impact: dict[str, float] = field(default_factory=dict)
    trace_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.decision_type not in ('TRADE', 'NO_TRADE', 'WAIT', 'SCALE_IN', 'SCALE_OUT', 'EXIT'):
            raise ValueError(f"Invalid decision type: {self.decision_type}")
        if self.direction not in ('LONG', 'SHORT', 'FLAT'):
            raise ValueError(f"Invalid direction: {self.direction}")
        if math.isnan(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Decision confidence out of bounds: {self.confidence}")

@dataclass(frozen=True)
class TradeBlueprint:
    """Complete trade execution plan generated by Risk Optimizer."""
    decision_id: str
    symbol: str
    exchange: str
    direction: str
    probability: float
    confidence: float
    expected_value: float
    position_size: float
    risk_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    tp1: float
    tp2: float
    tp3: float
    leverage: float = 1.0
    stop_model: str = "structure_hybrid"
    trade_quality_index: float = 0.0
    risk_reward_ratio: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.position_size, self.risk_size, self.entry_price, self.stop_loss, self.take_profit]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"TradeBlueprint contains NaN or Inf: {val}")
        if self.position_size < 0:
            raise ValueError("Position size cannot be negative")

@dataclass
class Position:
    """Open position - mutable living entity."""
    position_id: str
    blueprint_id: str
    symbol: str
    exchange: str
    direction: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: float = field(default_factory=time.time)
    current_price: float = 0.0
    floating_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    status: str = "OPEN"
    exit_price: float = 0.0
    exit_time: float = 0.0

    def __post_init__(self) -> None:
        for val in [self.entry_price, self.quantity, self.stop_loss, self.take_profit]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Position contains NaN or Inf: {val}")
        if self.entry_price <= 0 or self.quantity <= 0:
            raise ValueError("Entry price and quantity must be positive")
        if self.direction not in ('LONG', 'SHORT'):
            raise ValueError(f"Invalid direction: {self.direction}")

    def update_market_price(self, current_price: float) -> None:
        if math.isnan(current_price) or math.isinf(current_price) or current_price <= 0:
            return
        self.current_price = current_price
        if self.direction == "LONG":
            self.floating_pnl = (current_price - self.entry_price) * self.quantity
            self.max_favorable_excursion = max(self.max_favorable_excursion, current_price - self.entry_price)
            self.max_adverse_excursion = min(self.max_adverse_excursion, current_price - self.entry_price)
        else:
            self.floating_pnl = (self.entry_price - current_price) * self.quantity
            self.max_favorable_excursion = max(self.max_favorable_excursion, self.entry_price - current_price)
            self.max_adverse_excursion = min(self.max_adverse_excursion, self.entry_price - current_price)

    def close(self, exit_price: float, exit_time: float) -> 'Trade':
        if self.status != "OPEN":
            raise ValueError(f"Cannot close position {self.position_id} with status {self.status}")
        if self.direction == "LONG":
            self.realized_pnl = (exit_price - self.entry_price) * self.quantity
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.quantity
        self.floating_pnl = 0.0
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.status = "CLOSED"
        
        # Correct R-Multiple Calculation: Total PnL / Total Risk Amount
        risk_pts = abs(self.entry_price - self.stop_loss) if self.stop_loss > 0 else 1.0
        total_risk_amount = risk_pts * self.quantity
        r_multiple = self.realized_pnl / total_risk_amount if total_risk_amount > 0 else 0.0
        
        return Trade(
            trade_id=f"TRADE_{self.position_id}", position_id=self.position_id, symbol=self.symbol,
            direction=self.direction, entry_price=self.entry_price, exit_price=exit_price,
            quantity=self.quantity, pnl=self.realized_pnl, r_multiple=r_multiple, win=self.realized_pnl > 0
        )

@dataclass(frozen=True)
class Trade:
    """Closed trade record. Immutable."""
    trade_id: str
    position_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    r_multiple: float
    win: bool
    timestamp: float = field(default_factory=time.time)

```

### File: `src/apex/engines/__init__.py`
```python

```

### File: `src/apex/engines/decision_engine.py`
```python
"""Signal Decision Engine - The final decision authority."""
from __future__ import annotations

import time
from typing import Any

from ..domain.contracts import ProbabilityReport
from ..domain.trading import PortfolioState, Decision
from .governance import GovernanceEngine

class DecisionEngine:
    """Central decision kernel with multi-layer evaluation."""

    def __init__(self, governance: GovernanceEngine) -> None:
        self.governance = governance

    def evaluate(
        self,
        probability: ProbabilityReport,
        portfolio: PortfolioState,
        contributors_long: int = 0,
        contributors_short: int = 0,
    ) -> Decision:
        """Evaluate and produce final decision."""
        reasons: list[str] = []
        evidence: dict[str, float] = {}
        risk: dict[str, float] = {}
        portfolio_impact: dict[str, float] = {}

        # Layer 0: Kill Switch Check
        kill_triggered, kill_reason = self.governance.check_kill_switch(portfolio)
        if kill_triggered:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=1.0, priority=100,
                reasoning=(kill_reason, "Kill switch active"), risk_summary={"kill_switch": 1.0},
                timestamp=time.time()
            )

        # Layer 1: Portfolio Governance Check
        port_ok, port_reason = self.governance.check_portfolio_limits(portfolio)
        if not port_ok:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=1.0, priority=90,
                reasoning=(port_reason,), portfolio_impact={"blocked_by_governance": 1.0},
                timestamp=time.time()
            )

        # Layer 2: Decision Readiness & Uncertainty
        if probability.decision_readiness_index < self.governance.policy.min_decision_readiness:
            return Decision(
                decision_type="WAIT", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"DRI too low ({probability.decision_readiness_index:.2f})",),
                timestamp=time.time()
            )

        if probability.uncertainty > self.governance.policy.max_uncertainty:
            return Decision(
                decision_type="WAIT", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"Uncertainty too high ({probability.uncertainty:.2f})",),
                risk_summary={"uncertainty": probability.uncertainty}, timestamp=time.time()
            )

        # Layer 3: Probability & Edge Evaluation
        direction = "FLAT"
        chosen_prob = 0.0

        if probability.probability_long >= self.governance.policy.min_probability_threshold:
            if (probability.probability_long - probability.probability_short) >= self.governance.policy.min_prob_edge:
                if contributors_long >= self.governance.policy.min_contributors:
                    direction = "LONG"
                    chosen_prob = probability.probability_long
                    reasons.append(f"Long probability {probability.probability_long:.2f} above threshold")
                    evidence["probability_long"] = probability.probability_long
                else:
                    reasons.append(f"Insufficient long contributors ({contributors_long})")
            else:
                reasons.append("Long probability edge too small")
                
        elif probability.probability_short >= self.governance.policy.min_probability_threshold:
            if (probability.probability_short - probability.probability_long) >= self.governance.policy.min_prob_edge:
                if contributors_short >= self.governance.policy.min_contributors:
                    direction = "SHORT"
                    chosen_prob = probability.probability_short
                    reasons.append(f"Short probability {probability.probability_short:.2f} above threshold")
                    evidence["probability_short"] = probability.probability_short
                else:
                    reasons.append(f"Insufficient short contributors ({contributors_short})")
            else:
                reasons.append("Short probability edge too small")
        else:
            reasons.append("No probability above threshold")

        if direction == "FLAT":
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=probability.confidence,
                reasoning=tuple(reasons), evidence_summary=evidence, timestamp=time.time()
            )

        # Layer 4: Expected Value Check
        if probability.expected_r < self.governance.policy.min_expected_r:
            return Decision(
                decision_type="NO_TRADE", direction="FLAT", confidence=probability.confidence,
                reasoning=(f"Expected R too low ({probability.expected_r:.2f})", *reasons),
                evidence_summary=evidence, timestamp=time.time()
            )

        # Layer 5: Final Approval
        risk["uncertainty"] = probability.uncertainty
        risk["expected_drawdown"] = probability.expected_drawdown
        portfolio_impact["current_exposure"] = portfolio.total_exposure
        portfolio_impact["portfolio_heat"] = portfolio.portfolio_heat

        return Decision(
            decision_type="TRADE", direction=direction,
            confidence=chosen_prob * (1.0 - probability.uncertainty),
            utility=probability.expected_value, priority=int(chosen_prob * 100),
            reasoning=("All gates passed", *reasons), evidence_summary=evidence,
            risk_summary=risk, portfolio_impact=portfolio_impact, timestamp=time.time()
        )

```

### File: `src/apex/engines/execution_engine.py`
```python
"""Institutional Execution Engine - Manages order lifecycle and retries."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..core.interfaces import IExchangeAdapter
from ..domain.trading import TradeBlueprint

log = logging.getLogger(__name__)

class ExecutionEngine:
    """Orchestrates trade execution against an exchange."""

    def __init__(self, adapter: IExchangeAdapter, max_retries: int = 3) -> None:
        self.adapter = adapter
        self.max_retries = max_retries

    async def execute_blueprint(self, blueprint: TradeBlueprint) -> dict:
        """Execute a trade blueprint and handle retries on transient errors."""
        
        retry_count = 0
        last_response = {}
        
        while retry_count <= self.max_retries:
            log.info(f"Placing order attempt {retry_count + 1} for {blueprint.symbol} {blueprint.direction}")
            
            response = await self.adapter.place_order(blueprint)
            last_response = response
            
            # Check if response indicates success
            if "orderId" in response and response.get("status") in ["NEW", "PARTIALLY_FILLED", "FILLED"]:
                log.info(f"Order {response['orderId']} accepted with status {response['status']}")
                return response
                
            # Check if rejection is transient (e.g., rate limit -1015, timeout -1007)
            error_code = response.get("code", 0)
            if error_code in [-1015, -1007, -1000] and retry_count < self.max_retries:
                log.warning(f"Transient error {error_code}, retrying in 1s...")
                await asyncio.sleep(1.0)
                retry_count += 1
                continue
            else:
                log.error(f"Order permanently rejected: {response.get('msg')}")
                return response

        return last_response

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an active order."""
        return await self.adapter.cancel_order(order_id, symbol)

```

### File: `src/apex/engines/governance.py`
```python
"""Governance Layer - Enforces macro-level system rules."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class GovernancePolicy:
    """Configuration for governance rules."""
    max_concurrent_trades: int = 5
    max_drawdown_limit: float = 0.15  # 15% max drawdown
    min_decision_readiness: float = 0.40
    max_uncertainty: float = 0.45
    min_probability_threshold: float = 0.62
    min_prob_edge: float = 0.03
    min_contributors: int = 3
    min_expected_r: float = 0.10

class GovernanceEngine:
    """Evaluates decisions against hard limits."""

    def __init__(self, policy: GovernancePolicy) -> None:
        self.policy = policy

    def check_portfolio_limits(self, portfolio_state: Any) -> tuple[bool, str]:
        """Check if portfolio allows new trades."""
        if portfolio_state.open_positions_count >= self.policy.max_concurrent_trades:
            return False, f"Max concurrent trades reached ({self.policy.max_concurrent_trades})"
        
        if portfolio_state.risk_budget_used >= portfolio_state.risk_budget:
            return False, "Daily risk budget exhausted"
            
        if portfolio_state.drawdown >= self.policy.max_drawdown_limit:
            return False, f"Max drawdown limit reached ({self.policy.max_drawdown_limit*100}%)"
            
        return True, "Portfolio limits OK"

    def check_kill_switch(self, portfolio_state: Any) -> tuple[bool, str]:
        """Check if system kill switch should be activated."""
        if portfolio_state.health_score < 0.3:
            return True, "Portfolio health critical"
        return False, "Health nominal"

```

### File: `src/apex/engines/portfolio_engine.py`
```python
"""Portfolio Intelligence Engine - Manages capital, risk, and positions."""
from __future__ import annotations

import math
import time
from typing import Dict, List

from ..domain.trading import Position, Trade, PortfolioState

class PortfolioEngine:
    """Portfolio-level intelligence and management."""

    def __init__(self, initial_capital: float = 10000.0, max_drawdown: float = 0.15) -> None:
        self.initial_capital: float = initial_capital
        self.max_drawdown_limit: float = max_drawdown
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.realized_pnl: float = 0.0
        self.peak_equity: float = initial_capital
        self.kill_switch_active: bool = False

    @property
    def floating_pnl(self) -> float:
        return sum(p.floating_pnl for p in self.open_positions.values() if p.status == "OPEN")

    @property
    def total_equity(self) -> float:
        return self.initial_capital + self.realized_pnl + self.floating_pnl

    @property
    def total_exposure(self) -> float:
        return sum(p.quantity * p.current_price for p in self.open_positions.values() if p.status == "OPEN")

    @property
    def current_drawdown(self) -> float:
        if self.peak_equity <= 0: return 0.0
        return max(0.0, (self.peak_equity - self.total_equity) / self.peak_equity)

    def update_positions(self, market_prices: Dict[str, float]) -> None:
        for symbol, price in market_prices.items():
            for pos in self.open_positions.values():
                if pos.symbol == symbol and pos.status == "OPEN":
                    pos.update_market_price(price)
        if self.total_equity > self.peak_equity:
            self.peak_equity = self.total_equity
        if self.current_drawdown >= self.max_drawdown_limit and not self.kill_switch_active:
            self.kill_switch_active = True

    def add_position(self, position: Position) -> bool:
        if self.kill_switch_active: return False
        if position.position_id in self.open_positions: return False
        self.open_positions[position.position_id] = position
        return True

    def close_position(self, position_id: str, exit_price: float) -> Trade | None:
        position = self.open_positions.get(position_id)
        if position is None or position.status != "OPEN": return None
        
        trade = position.close(exit_price, time.time())
        self.realized_pnl += trade.pnl
        self.closed_trades.append(trade)
        
        if self.total_equity > self.peak_equity:
            self.peak_equity = self.total_equity
            
        # اصلاح: حذف پوزیشن بسته شده از لیست پوزیشن‌های باز
        del self.open_positions[position_id]
        
        return trade

    def get_state(self) -> PortfolioState:
        open_count = len(self.open_positions)  # حالا فقط پوزیشن‌های باز را شامل می‌شود
        health = max(0.0, 1.0 - (self.current_drawdown / self.max_drawdown_limit))
        return PortfolioState(
            total_equity=self.total_equity,
            available_capital=max(0.0, self.total_equity - self.total_exposure),
            total_exposure=self.total_exposure,
            open_positions_count=open_count,
            risk_budget=3.0,
            risk_budget_used=0.0,
            portfolio_heat=0.0,
            drawdown=self.current_drawdown,
            health_score=health
        )

```

### File: `src/apex/engines/probability_engine.py`
```python
"""Institutional Probability Engine v2 - Bayesian inference with ensemble models."""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..domain.contracts import ProbabilityReport

def _squash(x: float) -> float:
    if math.isnan(x): x = 0.0
    return 1.0 / (1.0 + math.exp(-x))

def _clamp(x: float, lo: float, hi: float) -> float:
    if math.isnan(x): return (lo + hi) / 2.0
    return max(lo, min(hi, x))

def _entropy_01(p: float) -> float:
    p = _clamp(p, 0.0001, 0.9999)
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p)) / math.log(2.0)

@dataclass
class BayesianModel:
    alpha: float = 6.0
    beta: float = 6.0
    r_sum: float = 0.0
    trades: float = 0.0

    @property
    def posterior(self) -> float:
        return self.alpha / max(self.alpha + self.beta, 0.0001)

    @property
    def expected_r(self) -> float:
        return self.r_sum / self.trades if self.trades > 0 else 0.0

    @property
    def sample_factor(self) -> float:
        return _clamp(self.trades / 25.0, 0.0, 1.0)

    def update(self, score: float, win: bool, r: float) -> None:
        s = _clamp(score, 0.0, 1.0)
        if s >= 0.20:
            self.alpha += s if win else 0.0
            self.beta += 0.0 if win else s
            self.r_sum += r * s
            self.trades += s

@dataclass
class CalibrationBin:
    wins: float = 0.0
    trades: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins + 1.0) / (self.trades + 2.0)

class ProbabilityEngine:
    def __init__(self, min_sample: float = 25.0, max_blend: float = 0.65) -> None:
        self.feature_models: list[BayesianModel] = [BayesianModel() for _ in range(13)]
        self.setup_models: dict[str, BayesianModel] = {}
        self.calibration_bins: list[CalibrationBin] = [CalibrationBin() for _ in range(10)]
        self.min_sample: float = min_sample
        self.max_blend: float = max_blend

    def calibrate(self, prob: float) -> float:
        pp = _clamp(prob, 0.01, 0.99)
        bin_idx = min(int(math.floor(pp * 10.0)), 9)
        cal_bin = self.calibration_bins[bin_idx]
        blend = _clamp(cal_bin.trades / self.min_sample, 0.0, self.max_blend)
        wr = cal_bin.win_rate
        return _clamp(pp * (1.0 - blend) + wr * blend, 0.01, 0.99)

    def update_calibration(self, prob: float, win: bool) -> None:
        bin_idx = min(int(math.floor(_clamp(prob, 0.0, 0.9999) * 10.0)), 9)
        self.calibration_bins[bin_idx].trades += 1.0
        if win:
            self.calibration_bins[bin_idx].wins += 1.0

    def update_feature_model(self, idx: int, score: float, win: bool, r: float) -> None:
        if 0 <= idx < len(self.feature_models):
            self.feature_models[idx].update(score, win, r)

    def update_setup(self, name: str, win: bool, r: float) -> None:
        if name not in self.setup_models:
            self.setup_models[name] = BayesianModel()
        self.setup_models[name].update(0.5, win, r)

    def compute_probability(
        self,
        evidence_long: dict[str, float],
        evidence_short: dict[str, float],
        weights: dict[str, float],
        trend_confidence: float = 0.5,
        interactions_long: float = 0.0,
        interactions_short: float = 0.0,
        penalties_long: float = 0.0,
        penalties_short: float = 0.0,
        crypto_bonus_long: float = 0.0,
        crypto_bonus_short: float = 0.0,
    ) -> ProbabilityReport:
        base_long = 0.0
        base_short = 0.0
        w_sum = sum(weights.values()) if weights else 1.0
        attribution: dict[str, float] = {}

        for key, weight in weights.items():
            ev_l = evidence_long.get(key, 0.0)
            ev_s = evidence_short.get(key, 0.0)
            w = weight / w_sum if w_sum > 0 else 0.0
            base_long += w * ev_l
            base_short += w * ev_s
            attribution[key] = (ev_l - ev_s) * w

        raw_long = base_long + interactions_long + crypto_bonus_long - penalties_long
        raw_short = base_short + interactions_short + crypto_bonus_short - penalties_short

        cal_gain = 5.4 + trend_confidence * 1.2
        prob_long_raw = _squash((raw_long - 0.45) * cal_gain)
        prob_short_raw = _squash((raw_short - 0.45) * cal_gain)

        prob_long = self.calibrate(prob_long_raw)
        prob_short = self.calibrate(prob_short_raw)
        
        max_prob = max(prob_long, prob_short)
        min_prob = min(prob_long, prob_short)
        prob_neutral = max(0.0, 1.0 - (max_prob + min_prob))
        
        total = prob_long + prob_short + prob_neutral
        prob_long /= total
        prob_short /= total
        prob_neutral /= total

        ambiguity = 1.0 - abs(prob_long - prob_short)
        uncertainty = _clamp(0.38 * ambiguity + 0.28 * _entropy_01(max_prob) + 0.34 * 0.5, 0.0, 1.0)
        
        confidence_long = prob_long * (1.0 - uncertainty)
        confidence_short = prob_short * (1.0 - uncertainty)
        confidence = max(confidence_long, confidence_short)

        base_rr = 3.5 / 2.0
        tp3_rr = base_rr * 1.50

        catalyst_l = max(evidence_long.values()) if evidence_long else 0.0
        catalyst_s = max(evidence_short.values()) if evidence_short else 0.0
        
        expected_rr_long = tp3_rr * _clamp(0.75 + 0.20 * 1.0 + 0.15 * catalyst_l - 0.10 * uncertainty, 0.50, 1.30)
        expected_rr_short = tp3_rr * _clamp(0.75 + 0.20 * 1.0 + 0.15 * catalyst_s - 0.10 * uncertainty, 0.50, 1.30)

        expected_r_long = prob_long * expected_rr_long - (1.0 - prob_long) - 0.02
        expected_r_short = prob_short * expected_rr_short - (1.0 - prob_short) - 0.02

        scenario_dist = {
            "trend_continuation": prob_long,
            "trend_failure": prob_short,
            "range": prob_neutral
        }

        dri = _clamp(
            (1.0 - uncertainty) * 0.30 +
            max(prob_long, prob_short) * 0.25 +
            (1.0 - _entropy_01(max_prob)) * 0.20 +
            0.25 * 1.0,
            0.0, 1.0
        )

        return ProbabilityReport(
            probability_long=prob_long,
            probability_short=prob_short,
            probability_neutral=prob_neutral,
            confidence=confidence,
            uncertainty=uncertainty,
            entropy=_entropy_01(max_prob),
            consensus=abs(prob_long - prob_short),
            calibration_score=1.0 - abs(prob_long - 0.5) * 0.5,
            expected_value=max(expected_r_long, expected_r_short),
            expected_r=max(expected_r_long, expected_r_short),
            expected_rr=max(expected_rr_long, expected_rr_short),
            expected_drawdown=uncertainty * 0.5,
            expected_adverse_excursion=0.5,
            expected_favorable_excursion=1.5,
            trade_survival_probability=max(prob_long, prob_short) * (1.0 - uncertainty),
            expected_holding_time=12,
            scenario_distribution=scenario_dist,
            feature_attribution=attribution,
            evidence_summary={**evidence_long, **{f"{k}_s": v for k, v in evidence_short.items()}},
            regime="neutral",
            decision_readiness_index=dri,
            model_version="2.0.0",
            health_score=1.0,
        )

```

### File: `src/apex/engines/risk_engine.py`
```python
"""Risk, Money Management & Execution Optimizer."""
from __future__ import annotations

import math
from typing import Any
import uuid

from ..domain.contracts import ProbabilityReport
from ..domain.trading import PortfolioState, TradeBlueprint, Decision

class RiskEngine:
    """Calculates optimal trade parameters and position sizing."""

    def __init__(self, risk_per_trade_pct: float = 1.0, sl_mult: float = 2.0, tp_mult: float = 3.5) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.fee_slippage_r: float = 0.02

    def _clamp(self, x: float, lo: float, hi: float) -> float:
        if math.isnan(x):
            return (lo + hi) / 2.0
        return max(lo, min(hi, x))

    def compute_stop_loss(
        self,
        entry_price: float,
        atr: float,
        direction: str,
        structure_low: float | None = None,
        structure_high: float | None = None,
        ob_bot: float | None = None,
        ob_top: float | None = None,
    ) -> float:
        """Compute stop loss using Structure Hybrid model."""
        if direction == "LONG":
            atr_sl = entry_price - (atr * self.sl_mult)
            
            struct_sl = None
            if ob_bot is not None and ob_bot > 0:
                struct_sl = ob_bot - (atr * 0.15)
            elif structure_low is not None and structure_low > 0:
                struct_sl = structure_low - (atr * 0.15)
                
            if struct_sl is not None and struct_sl > 0:
                risk_struct = entry_price - struct_sl
                max_risk = atr * self.sl_mult * 1.60
                min_risk = atr * 0.35
                if min_risk < risk_struct <= max_risk:
                    return struct_sl
                    
            return atr_sl
            
        else:  # SHORT
            atr_sl = entry_price + (atr * self.sl_mult)
            
            struct_sl = None
            if ob_top is not None and ob_top > 0:
                struct_sl = ob_top + (atr * 0.15)
            elif structure_high is not None and structure_high > 0:
                struct_sl = structure_high + (atr * 0.15)
                
            if struct_sl is not None and struct_sl > 0:
                risk_struct = struct_sl - entry_price
                max_risk = atr * self.sl_mult * 1.60
                min_risk = atr * 0.35
                if min_risk < risk_struct <= max_risk:
                    return struct_sl
                    
            return atr_sl

    def compute_take_profit(
        self,
        entry_price: float,
        stop_price: float,
        direction: str,
        htf_high: float | None = None,
        htf_low: float | None = None,
    ) -> tuple[float, float, float, float]:
        """Compute TP1, TP2, TP3 and final TP using liquidity targets."""
        risk_pts = abs(entry_price - stop_price)
        if risk_pts <= 0:
            return entry_price, entry_price, entry_price, entry_price

        base_rr = self.tp_mult / self.sl_mult

        if direction == "LONG":
            tp1 = entry_price + (risk_pts * base_rr * 0.50)
            tp2 = entry_price + (risk_pts * base_rr)
            tp3_candidate = entry_price + (risk_pts * base_rr * 1.50)
            
            if htf_high is not None and htf_high > tp2 and htf_high < tp3_candidate:
                tp3 = htf_high
            else:
                tp3 = tp3_candidate
        else:  # SHORT
            tp1 = entry_price - (risk_pts * base_rr * 0.50)
            tp2 = entry_price - (risk_pts * base_rr)
            tp3_candidate = entry_price - (risk_pts * base_rr * 1.50)
            
            if htf_low is not None and htf_low < tp2 and htf_low > tp3_candidate:
                tp3 = htf_low
            else:
                tp3 = tp3_candidate

        return tp1, tp2, tp3, tp3

    def compute_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0
    ) -> tuple[float, float]:
        """Calculate position size based on risk percentage."""
        risk_amount = capital * (self.risk_per_trade_pct / 100.0)
        risk_per_unit = abs(entry_price - stop_price)
        
        if risk_per_unit <= 0 or entry_price <= 0:
            return 0.0, 0.0
            
        position_size = risk_amount / risk_per_unit
        
        max_notional = capital * leverage
        max_size = max_notional / entry_price
        
        final_size = min(position_size, max_size)
        actual_risk = final_size * risk_per_unit
        
        return final_size, actual_risk

    def create_blueprint(
        self,
        decision: Decision,
        portfolio: PortfolioState,
        probability_report: ProbabilityReport,
        current_price: float,
        atr: float,
        structure_low: float | None = None,
        structure_high: float | None = None,
        ob_bot: float | None = None,
        ob_top: float | None = None,
        htf_high: float | None = None,
        htf_low: float | None = None,
    ) -> TradeBlueprint | None:
        """Create the complete trade execution blueprint."""
        
        if decision.decision_type != "TRADE":
            return None
            
        if atr <= 0 or current_price <= 0:
            return None

        stop_loss = self.compute_stop_loss(
            current_price, atr, decision.direction,
            structure_low, structure_high, ob_bot, ob_top
        )

        tp1, tp2, tp3, tp = self.compute_take_profit(
            current_price, stop_loss, decision.direction, htf_high, htf_low
        )

        position_size, risk_size = self.compute_position_size(
            portfolio.available_capital, current_price, stop_loss
        )

        if position_size <= 0:
            return None

        risk_pts = abs(current_price - stop_loss)
        reward_pts = abs(tp - current_price)
        rr = reward_pts / risk_pts if risk_pts > 0 else 0.0
        
        tqi = self._clamp(
            probability_report.probability_long * 0.30 +
            decision.confidence * 0.20 +
            probability_report.expected_value * 0.20 +
            (1.0 - probability_report.uncertainty) * 0.15 +
            self._clamp(rr / 3.0, 0.0, 1.0) * 0.15,
            0.0, 1.0
        )

        return TradeBlueprint(
            decision_id=decision.trace_id or str(uuid.uuid4()),
            symbol="BTC-SWAP-USDT",  # Hardcoded for test, will be dynamic in production
            exchange="toobit",
            direction=decision.direction,
            probability=probability_report.probability_long if decision.direction == "LONG" else probability_report.probability_short,
            confidence=decision.confidence,
            expected_value=probability_report.expected_value,
            position_size=position_size,
            risk_size=risk_size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=tp,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            trade_quality_index=tqi,
            risk_reward_ratio=rr
        )

```

### File: `src/apex/features/__init__.py`
```python

```

### File: `src/apex/features/feature_store.py`
```python
"""Institutional Feature Store with Dependency Graph and 3-tier architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict, deque
import time
import hashlib
import math
from enum import Enum

class FeatureCategory(Enum):
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    TREND = "trend"
    MOMENTUM = "momentum"
    LIQUIDITY = "liquidity"

@dataclass(frozen=True)
class Feature:
    """Standardized feature object. Immutable and validated."""
    feature_id: str
    name: str
    category: FeatureCategory
    version: str = "1.0.0"
    value: float = 0.0
    normalized_value: float = 0.0
    confidence: float = 1.0
    reliability: float = 1.0
    quality: float = 1.0
    importance: float = 0.0
    weight: float = 0.0
    age: float = 0.0
    timestamp: float = field(default_factory=time.time)
    timeframe: str = "1m"
    symbol: str = ""
    exchange: str = ""
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    normalization_method: str = "zscore"
    calculation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.value, self.normalized_value, self.confidence, self.reliability, self.quality]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Feature '{self.name}' contains NaN or Inf: {val}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Feature confidence must be in [0, 1], got {self.confidence}")

    @property
    def hash(self) -> str:
        content = f"{self.name}:{self.version}:{self.value}:{self.timestamp}:{self.symbol}:{self.timeframe}"
        return hashlib.sha256(content.encode()).hexdigest()

class FeatureStore:
    """Three-tier feature store with dependency resolution."""

    def __init__(self, max_warm_size: int = 10000, max_cold_size: int = 100000) -> None:
        self._hot: dict[str, Feature] = {}
        self._warm: dict[str, deque[Feature]] = defaultdict(lambda: deque(maxlen=max_warm_size))
        self._cold: dict[str, list[Feature]] = defaultdict(list)
        self._max_cold_size = max_cold_size
        self._registry: dict[str, dict[str, Any]] = {}
        self._dependency_graph: dict[str, list[str]] = {}

    def _key(self, name: str, symbol: str, timeframe: str) -> str:
        return f"{name}:{symbol}:{timeframe}"

    def register(self, name: str, category: FeatureCategory, dependencies: list[str] = [], **meta: Any) -> None:
        self._registry[name] = {"category": category, "registered_at": time.time(), **meta}
        self._dependency_graph[name] = dependencies

    def are_dependencies_ready(self, name: str, symbol: str, timeframe: str, current_timestamp: float, max_age_sec: float = 60.0) -> bool:
        deps = self._dependency_graph.get(name, [])
        for dep_name in deps:
            key = self._key(dep_name, symbol, timeframe)
            feature = self._hot.get(key)
            if feature is None:
                return False
            if (current_timestamp - feature.timestamp) > max_age_sec:
                return False
        return True

    def store(self, feature: Feature) -> None:
        key = self._key(feature.name, feature.symbol, feature.timeframe)
        self._hot[key] = feature
        self._warm[key].append(feature)
        self._cold[key].append(feature)
        if len(self._cold[key]) > self._max_cold_size:
            self._cold[key].pop(0)

    def get(self, name: str, symbol: str = "", timeframe: str = "1m") -> Feature | None:
        return self._hot.get(self._key(name, symbol, timeframe))

    def get_history(self, name: str, symbol: str = "", timeframe: str = "1m", limit: int = 100) -> list[Feature]:
        key = self._key(name, symbol, timeframe)
        return list(self._warm[key])[-limit:]

```

### File: `src/apex/features/indicators.py`
```python
"""Math helper functions for feature calculations."""
from __future__ import annotations
import math

def clamp(x: float, lo: float, hi: float) -> float:
    if math.isnan(x):
        return (lo + hi) / 2.0
    return max(lo, min(hi, x))

def entropy_01(p: float) -> float:
    p = clamp(p, 0.0001, 0.9999)
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p)) / math.log(2.0)

def percentile_rank(data: list, value: float) -> float:
    if not data:
        return 0.5
    count_below = sum(1 for v in data if v < value)
    return count_below / len(data) if len(data) > 0 else 0.5

```

### File: `src/apex/features/primitives.py`
```python
"""Primitive feature calculations with numerical stability guarantees."""
from __future__ import annotations

import math
from typing import Sequence
import time

from ..domain.market import MarketBar
from .feature_store import Feature, FeatureStore, FeatureCategory

class PrimitiveFeatures:
    """Calculates base features from raw market data."""

    def __init__(self, store: FeatureStore) -> None:
        self.store = store
        self.store.register("ATR", FeatureCategory.VOLATILITY, dependencies=[])
        self.store.register("RSI", FeatureCategory.MOMENTUM, dependencies=[])

    def calculate_atr(self, bars: Sequence[MarketBar], period: int = 14, symbol: str = "", timeframe: str = "1m") -> Feature:
        """Average True Range with Wilder's Smoothing. No NaN propagation."""
        if len(bars) < period + 1:
            value = 0.0
            confidence = 0.0
        else:
            trs = []
            for i in range(1, len(bars)):
                bar = bars[i]
                prev_close = bars[i-1].close
                tr = max(
                    bar.high - bar.low,
                    abs(bar.high - prev_close),
                    abs(bar.low - prev_close)
                )
                trs.append(tr)
            
            atr = sum(trs[:period]) / period
            for i in range(period, len(trs)):
                atr = (atr * (period - 1) + trs[i]) / period
            
            if math.isnan(atr) or math.isinf(atr) or atr <= 0:
                value = 0.0
                confidence = 0.1
            else:
                value = atr
                confidence = 1.0

        feature = Feature(
            feature_id=f"ATR_{symbol}_{timeframe}_{int(time.time())}",
            name="ATR",
            category=FeatureCategory.VOLATILITY,
            value=value,
            confidence=confidence,
            symbol=symbol,
            timeframe=timeframe,
            dependencies=(),
            metadata={"period": period}
        )
        self.store.store(feature)
        return feature

    def calculate_rsi(self, bars: Sequence[MarketBar], period: int = 14, symbol: str = "", timeframe: str = "1m") -> Feature:
        """Relative Strength Index with division-by-zero protection."""
        if len(bars) < period + 1:
            value = 50.0
            confidence = 0.0
        else:
            gains = []
            losses = []
            for i in range(1, len(bars)):
                diff = bars[i].close - bars[i-1].close
                gains.append(max(0.0, diff))
                losses.append(max(0.0, -diff))

            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period

            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                value = 100.0 if avg_gain > 0 else 50.0
            else:
                rs = avg_gain / avg_loss
                value = 100.0 - (100.0 / (1.0 + rs))
            
            if math.isnan(value) or math.isinf(value):
                value = 50.0
                confidence = 0.1
            else:
                confidence = 1.0

        feature = Feature(
            feature_id=f"RSI_{symbol}_{timeframe}_{int(time.time())}",
            name="RSI",
            category=FeatureCategory.MOMENTUM,
            value=value,
            confidence=confidence,
            symbol=symbol,
            timeframe=timeframe,
            dependencies=(),
            metadata={"period": period}
        )
        self.store.store(feature)
        return feature

```

### File: `src/apex/features/regime_engine.py`
```python
"""Institutional Regime Intelligence Engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from ..domain.market import MarketBar
from .indicators import clamp

@dataclass(frozen=True)
class RegimeState:
    trend_class: str = "NEUTRAL"
    trend_confidence: float = 0.5

class RegimeEngine:
    def detect_regime(self, bars: Sequence[MarketBar]) -> RegimeState:
        if len(bars) < 20:
            return RegimeState()
        closes = [b.close for b in bars]
        ema_fast = sum(closes[-10:]) / 10
        ema_slow = sum(closes[-20:]) / 20
        
        if ema_fast > ema_slow:
            return RegimeState(trend_class="BULL", trend_confidence=0.7)
        elif ema_fast < ema_slow:
            return RegimeState(trend_class="BEAR", trend_confidence=0.7)
        return RegimeState(trend_class="NEUTRAL", trend_confidence=0.4)

```

### File: `src/apex/features/structure.py`
```python
"""Institutional Market Structure, Order Blocks, and Fair Value Gaps."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from ..domain.market import MarketBar
from .indicators import clamp

@dataclass(frozen=True)
class StructureState:
    trend_dir: int = 0
    bos_up: bool = False
    bos_dn: bool = False
    choch_up: bool = False
    choch_dn: bool = False

@dataclass(frozen=True)
class OrderBlock:
    top: float
    bot: float
    confidence: float
    quality: float
    born_index: int

@dataclass(frozen=True)
class FairValueGap:
    top: float
    bot: float
    confidence: float

def detect_pivots(highs: Sequence[float], lows: Sequence[float], left: int, right: int):
    if len(highs) < left + right + 1:
        return None, None
    idx = len(highs) - 1 - right
    if idx < left:
        return None, None
    pivot_high = highs[idx]
    pivot_low = lows[idx]
    is_ph = True
    is_pl = True
    for i in range(idx - left, idx + right + 1):
        if i == idx: continue
        if highs[i] >= pivot_high: is_ph = False
        if lows[i] <= pivot_low: is_pl = False
    return (pivot_high if is_ph else None), (pivot_low if is_pl else None)

def update_structure(state: StructureState, highs, lows, closes, atr, pivot_lb=8, eq_tol=0.10, disp_atr=1.20):
    ph, pl = detect_pivots(highs, lows, pivot_lb, pivot_lb)
    trend_dir = state.trend_dir
    bos_up, bos_dn = False, False
    choch_up, choch_dn = False, False
    
    # Simplified structure break logic
    close = closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else close
    
    if ph is not None and ph > 0 and close > ph and prev_close <= ph:
        if trend_dir == -1:
            choch_up = True
        else:
            bos_up = True
        trend_dir = 1
        
    elif pl is not None and pl > 0 and close < pl and prev_close >= pl:
        if trend_dir == 1:
            choch_dn = True
        else:
            bos_dn = True
        trend_dir = -1
        
    return StructureState(
        trend_dir=trend_dir, bos_up=bos_up, bos_dn=bos_dn,
        choch_up=choch_up, choch_dn=choch_dn
    )

def detect_order_blocks(bars: Sequence[MarketBar], bos_up: bool, bos_dn: bool, max_lookback: int = 5):
    obs = []
    if bos_up:
        for i in range(1, min(len(bars), max_lookback)):
            if bars[i].close < bars[i].open:
                obs.append(OrderBlock(top=bars[i].high, bot=bars[i].low, confidence=0.8, quality=0.8, born_index=i))
                break
    if bos_dn:
        for i in range(1, min(len(bars), max_lookback)):
            if bars[i].close > bars[i].open:
                obs.append(OrderBlock(top=bars[i].high, bot=bars[i].low, confidence=0.8, quality=0.8, born_index=i))
                break
    return obs

def detect_fvgs(bars: Sequence[MarketBar]):
    if len(bars) < 3: return None, None
    bull_fvg = None
    bear_fvg = None
    if bars[-1].low > bars[-3].high:
        bull_fvg = FairValueGap(top=bars[-1].low, bot=bars[-3].high, confidence=0.8)
    if bars[-1].high < bars[-3].low:
        bear_fvg = FairValueGap(top=bars[-3].low, bot=bars[-1].high, confidence=0.8)
    return bull_fvg, bear_fvg

```

### File: `src/apex/infrastructure/__init__.py`
```python

```

### File: `src/apex/infrastructure/data_validator.py`
```python
"""Data Validation Engine - Implements the strict validation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from ..domain.market import MarketBar, Tick, OrderBook

@dataclass(frozen=True)
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    quality_score: float
    errors: list[str]
    warnings: list[str]

class DataValidator:
    """Validates raw market data against APEX standards."""

    def validate_tick(self, tick: Tick, expected_symbol: str = "") -> ValidationResult:
        errors = []
        warnings = []
        score = 1.0

        if expected_symbol and tick.symbol != expected_symbol:
            errors.append(f"Symbol mismatch: expected {expected_symbol}, got {tick.symbol}")
        
        if tick.timestamp <= 0:
            errors.append("Invalid timestamp")
        
        if tick.receive_time > 0 and tick.receive_time < tick.timestamp:
            warnings.append("Receive time is before exchange time (clock drift)")
            score -= 0.1

        if tick.side not in ('buy', 'sell'):
            errors.append(f"Invalid side: {tick.side}")

        if errors:
            return ValidationResult(False, 0.0, errors, warnings)

        return ValidationResult(True, max(0.0, score), errors, warnings)

    def validate_bar(self, bar: MarketBar, tick_size: float = 0.0) -> ValidationResult:
        errors = []
        warnings = []
        score = 1.0

        # 1. Precision Validation
        if tick_size > 0:
            for val in [bar.open, bar.high, bar.low, bar.close]:
                remainder = val % tick_size
                if remainder > 1e-9 and abs(remainder - tick_size) > 1e-9:
                    warnings.append(f"Precision mismatch with tick_size {tick_size}")
                    score -= 0.05

        # 2. Volume Validation
        if bar.volume < 0:
            errors.append("Negative volume")
        
        # 3. Flash Event Detection
        if bar.range > 0 and bar.body > 0:
            if bar.range > (bar.close * 0.10) and bar.body_frac < 0.05:
                warnings.append("Flash event detected: High range, low body")
                score -= 0.3

        if errors:
            return ValidationResult(False, 0.0, errors, warnings)

        return ValidationResult(True, max(0.0, score), errors, warnings)

    def validate_orderbook(self, book: OrderBook) -> ValidationResult:
        errors = []
        warnings = []
        score = 1.0

        if not book.bids or not book.asks:
            errors.append("OrderBook is empty")
            return ValidationResult(False, 0.0, errors, warnings)

        if book.best_bid >= book.best_ask:
            errors.append(f"Crossed orderbook: bid {book.best_bid} >= ask {book.best_ask}")

        if len(book.bids) < 5 or len(book.asks) < 5:
            warnings.append("Shallow orderbook depth")
            score -= 0.1

        if book.spread_bps > 50:
            warnings.append(f"Abnormally high spread: {book.spread_bps} bps")
            score -= 0.2

        if errors:
            return ValidationResult(False, 0.0, errors, warnings)

        return ValidationResult(True, max(0.0, score), errors, warnings)

```

### File: `src/apex/infrastructure/exchanges/__init__.py`
```python

```

### File: `src/apex/infrastructure/exchanges/toobit_adapter.py`
```python
"""Toobit Exchange Adapter - Implements IExchangeAdapter."""
from __future__ import annotations

import math
from typing import Any

from ...core.interfaces import IExchangeAdapter
from ...domain.trading import TradeBlueprint
from .toobit_client import ToobitClient, ToobitClientError

class ToobitAdapter(IExchangeAdapter):
    """Adapter for Toobit Exchange."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.client = ToobitClient(api_key, api_secret)

    def _map_direction_to_side(self, direction: str) -> str:
        """Maps APEX direction to Toobit side (BUY_OPEN / SELL_OPEN)."""
        if direction == "LONG": return "BUY_OPEN"
        elif direction == "SHORT": return "SELL_OPEN"
        raise ValueError(f"Invalid direction for order placement: {direction}")

    async def place_order(self, blueprint: TradeBlueprint) -> dict:
        """Place order on Toobit and return raw response dict."""
        params = {
            "symbol": blueprint.symbol,
            "side": self._map_direction_to_side(blueprint.direction),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(blueprint.position_size),
            "price": str(blueprint.entry_price),
            "priceType": "INPUT",
            "newClientOrderId": blueprint.decision_id
        }
        
        try:
            response = await self.client.place_futures_order(**params)
            return response
        except ToobitClientError as e:
            # Return a standardized error dict instead of raising exception
            return {"code": e.code, "msg": e.msg, "status": "REJECTED"}

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self.client.cancel_futures_order(symbol, order_id)
            return True
        except ToobitClientError:
            return False

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        # This would call GET /api/v1/futures/order in a real scenario
        # For simplicity in this phase, we return a mock
        return {"orderId": order_id, "status": "NEW"}

```

### File: `src/apex/infrastructure/exchanges/toobit_client.py`
```python
"""Toobit Exchange API Client - Low-level HTTP communication."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import socket
from typing import Any
import urllib.parse

import aiohttp

class ToobitClientError(Exception):
    """Exception raised for Toobit API errors."""
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")

class ToobitClient:
    """Low-level HTTP client for Toobit API."""

    BASE_URL = "https://api.toobit.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    def _generate_signature(self, query_string: str, request_body: str = "") -> str:
        total_payload = query_string + request_body
        secret_bytes = self.api_secret.encode('utf-8')
        payload_bytes = total_payload.encode('utf-8')
        signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
        return signature

    def _build_query_string(self, params: dict[str, Any]) -> str:
        filtered_params = {k: v for k, v in params.items() if v is not None}
        return urllib.parse.urlencode(filtered_params)

    async def _request(
        self, method: str, path: str, params: dict[str, Any] = None, 
        body: dict[str, Any] = None, signed: bool = True
    ) -> dict[str, Any] | list:
        params = params or {}
        body = body or {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 10000

        query_string = self._build_query_string(params)
        request_body_str = self._build_query_string(body) if body else ""
        
        url = f"{self.BASE_URL}{path}"
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret are required for signed endpoints")
            signature = self._generate_signature(query_string, request_body_str)
            headers["X-BB-APIKEY"] = self.api_key
            full_query = f"{query_string}&signature={signature}"
            url = f"{url}?{full_query}"
        else:
            if query_string:
                url = f"{url}?{query_string}"

        session = await self._get_session()
        
        try:
            async with session.request(method, url, data=request_body_str, headers=headers) as response:
                data = await response.json()
                if isinstance(data, dict) and "code" in data and data["code"] != 200:
                    raise ToobitClientError(data["code"], data.get("msg", "Unknown Error"))
                return data
        except aiohttp.ClientError as e:
            raise ToobitClientError(-1000, f"Network Error: {str(e)}")

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 50) -> list:
        """GET /quote/v1/klines - Fetch historical candlestick data."""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return await self._request("GET", "/quote/v1/klines", params=params, signed=False)

    async def place_futures_order(self, **params: Any) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/futures/order", body=params)

    async def cancel_futures_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        params = {"symbol": symbol, "orderId": order_id}
        return await self._request("DELETE", "/api/v1/futures/order", params=params)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

```

### File: `src/apex/infrastructure/exchanges/toobit_ws.py`
```python
"""Toobit WebSocket Client for real-time market data streams."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from ...domain.market import MarketBar, Tick
from ...core.events import Event, EventBus
from ...core.types.enums import EventType

log = logging.getLogger(__name__)

class ToobitWebSocketClient:
    """Manages WebSocket connection to Toobit."""

    BASE_URL = "wss://stream.toobit.com/quote/ws/v1"

    def __init__(self, event_bus: EventBus, symbols: list[str]) -> None:
        self.event_bus = event_bus
        self.symbols = symbols
        self._ws: Any = None
        self._running: bool = False
        self._reconnect_delay: float = 1.0

    async def connect(self) -> None:
        """Establish connection and start listening loop."""
        self._running = True
        while self._running:
            try:
                log.info(f"Connecting to Toobit WebSocket: {self.BASE_URL}")
                async with websockets.connect(self.BASE_URL, ping_interval=None) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1.0
                    
                    await self._subscribe_streams()
                    
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    listen_task = asyncio.create_task(self._listen_loop())
                    
                    await listen_task
                    
                    heartbeat_task.cancel()
                    
            except (ConnectionClosed, ConnectionError, asyncio.TimeoutError) as e:
                log.warning(f"Toobit WS disconnected: {e}. Reconnecting in {self._reconnect_delay}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)
            except Exception as e:
                log.error(f"Unexpected WS error: {e}", exc_info=True)
                await asyncio.sleep(5.0)
                
            finally:
                self._ws = None

    async def disconnect(self) -> None:
        """Gracefully disconnect from WebSocket."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()

    async def _subscribe_streams(self) -> None:
        """Subscribe to required market data streams."""
        trade_msg = {
            "symbol": ",".join(self.symbols),
            "topic": "trade",
            "event": "sub",
            "params": {"binary": "false"}
        }
        await self._ws.send(json.dumps(trade_msg))
        
        kline_msg = {
            "symbol": ",".join(self.symbols),
            "topic": "kline_1m",
            "event": "sub",
            "params": {"binary": "false"}
        }
        await self._ws.send(json.dumps(kline_msg))
        log.info(f"Subscribed to trades and 1m klines for {self.symbols}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic ping to keep connection alive."""
        while self._running and self._ws and not self._ws.closed:
            try:
                ping_msg = {"ping": int(time.time() * 1000)}
                await self._ws.send(json.dumps(ping_msg))
                await asyncio.sleep(30.0)
            except Exception:
                break

    async def _listen_loop(self) -> None:
        """Listen for incoming WebSocket messages."""
        async for raw_message in self._ws:
            try:
                data = json.loads(raw_message)
                await self._process_message(data)
            except json.JSONDecodeError:
                log.warning(f"Failed to decode WS message: {raw_message}")
            except Exception as e:
                log.error(f"Error processing WS message: {e}", exc_info=True)

    async def _process_message(self, data: dict[str, Any]) -> None:
        """Parse Toobit WS payload and publish domain events."""
        topic = data.get("topic")
        
        if "pong" in data or data.get("event") == "sub":
            return
            
        if not topic or "data" not in data:
            return

        symbol = data.get("symbol", "")
        payload_list = data.get("data", [])
        
        if topic == "trade":
            for item in payload_list:
                tick = Tick(
                    timestamp=int(item.get("t", 0)),
                    price=float(item.get("p", 0.0)),
                    volume=float(item.get("q", 0.0)),
                    side="sell" if item.get("m", False) else "buy",
                    symbol=symbol,
                    exchange="toobit"
                )
                await self.event_bus.publish(Event(
                    event_type=EventType.NEW_TICK,
                    source="toobit_ws",
                    payload={"tick": tick.__dict__}
                ))
                
        elif topic == "kline":
            for item in payload_list:
                open_time = int(item.get("t", 0))
                bar = MarketBar(
                    timestamp=open_time,
                    open=float(item.get("o", 0.0)),
                    high=float(item.get("h", 0.0)),
                    low=float(item.get("l", 0.0)),
                    close=float(item.get("c", 0.0)),
                    volume=float(item.get("v", 0.0)),
                    symbol=symbol,
                    exchange="toobit",
                    timeframe="1m"
                )
                await self.event_bus.publish(Event(
                    event_type=EventType.NEW_CANDLE,
                    source="toobit_ws",
                    payload={"bar": bar.__dict__}
                ))

```

### File: `src/apex/monitoring/__init__.py`
```python

```

### File: `src/apex/monitoring/contracts.py`
```python
"""Observability contracts and DTOs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math
import time

@dataclass(frozen=True)
class LogEntry:
    """Immutable structured log entry."""
    timestamp: float
    level: str  # INFO, WARNING, ERROR, CRITICAL
    module: str
    message: str
    trace_id: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Metric:
    """Metric data point for telemetry."""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Metric '{self.name}' contains NaN or Inf: {self.value}")

@dataclass(frozen=True)
class HealthReport:
    """Health status report for a system module."""
    module: str
    status: str  # HEALTHY, WARNING, CRITICAL, OFFLINE
    score: float
    last_heartbeat: float
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"Health score must be in [0, 1], got {self.score}")
        if self.status not in ('HEALTHY', 'WARNING', 'CRITICAL', 'OFFLINE'):
            raise ValueError(f"Invalid health status: {self.status}")

```

### File: `src/apex/monitoring/health_monitor.py`
```python
"""Health Monitor - Tracks heartbeat and status of all system modules."""
from __future__ import annotations

import time
from typing import Dict
import threading

from .contracts import HealthReport

class HealthMonitor:
    """Monitors the health and heartbeat of system services."""

    def __init__(self, heartbeat_timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._heartbeats: Dict[str, float] = {}
        self._statuses: Dict[str, HealthReport] = {}
        self._timeout: float = heartbeat_timeout

    def register_module(self, module: str) -> None:
        with self._lock:
            if module not in self._heartbeats:
                self._heartbeats[module] = time.time()
                self._statuses[module] = HealthReport(
                    module=module, status="HEALTHY", score=1.0, last_heartbeat=time.time()
                )

    def heartbeat(self, module: str) -> None:
        with self._lock:
            self._heartbeats[module] = time.time()

    def update_status(self, module: str, score: float, details: dict | None = None) -> None:
        with self._lock:
            current_time = time.time()
            self._heartbeats[module] = current_time
            if score >= 0.8: status = "HEALTHY"
            elif score >= 0.5: status = "WARNING"
            else: status = "CRITICAL"
            self._statuses[module] = HealthReport(
                module=module, status=status, score=score, 
                last_heartbeat=current_time, details=details or {}
            )

    def get_all_statuses(self) -> Dict[str, HealthReport]:
        with self._lock:
            current_time = time.time()
            result = {}
            for module, last_beat in self._heartbeats.items():
                if current_time - last_beat > self._timeout:
                    self._statuses[module] = HealthReport(
                        module=module, status="OFFLINE", score=0.0, last_heartbeat=last_beat,
                        details={"reason": "Heartbeat timeout"}
                    )
                result[module] = self._statuses[module]
            return result

```

### File: `src/apex/monitoring/metrics_engine.py`
```python
"""Metrics Engine - Real-time collection of system performance data."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List
import threading
import time

from .contracts import Metric

class MetricsEngine:
    """Thread-safe collection of system metrics."""

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.Lock()
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._max_history: int = max_history

    def record(self, name: str, value: float, unit: str = "", **tags: str) -> None:
        metric = Metric(name=name, value=value, unit=unit, tags=tags)
        with self._lock:
            self._metrics[name].append(metric)
            if len(self._metrics[name]) > self._max_history:
                self._metrics[name].pop(0)

    def get_latest(self, name: str) -> Metric | None:
        with self._lock:
            history = self._metrics.get(name, [])
            return history[-1] if history else None

    def get_history(self, name: str, limit: int = 100) -> List[Metric]:
        with self._lock:
            return list(self._metrics.get(name, [])[-limit:])

    def get_all_latest(self) -> Dict[str, Metric]:
        with self._lock:
            return {name: hist[-1] for name, hist in self._metrics.items() if hist}

```

### File: `src/apex/monitoring/structured_logger.py`
```python
"""Structured JSON Logger for enterprise-grade observability."""
from __future__ import annotations

import json
import sys
import time
from typing import Any
import logging

from .contracts import LogEntry

class StructuredLogger:
    """Outputs logs as structured JSON to stdout/stderr."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self._logger = logging.getLogger(module_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # جلوگیری از چاپ تکراری لاگ‌ها
        
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)

    def log(self, level: str, message: str, trace_id: str = "", **metadata: Any) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            level=level.upper(),
            module=self.module_name,
            message=message,
            trace_id=trace_id,
            metadata=metadata
        )
        
        log_dict = {
            "timestamp": entry.timestamp,
            "level": entry.level,
            "module": entry.module,
            "message": entry.message,
            "trace_id": entry.trace_id,
            **entry.metadata
        }
        
        log_str = json.dumps(log_dict, default=str)
        
        if entry.level in ["ERROR", "CRITICAL"]:
            self._logger.error(log_str)
        elif entry.level == "WARNING":
            self._logger.warning(log_str)
        else:
            self._logger.info(log_str)

    def info(self, message: str, **metadata: Any) -> None:
        self.log("INFO", message, **metadata)

    def warning(self, message: str, **metadata: Any) -> None:
        self.log("WARNING", message, **metadata)

    def error(self, message: str, **metadata: Any) -> None:
        self.log("ERROR", message, **metadata)

```

### File: `src/apex/research/__init__.py`
```python

```

### File: `src/apex/research/knowledge_base.py`
```python
"""Knowledge Base - Long-term memory and experience repository."""
from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Any
import threading

from ..domain.knowledge import Experience, Knowledge

class KnowledgeBase:
    """Thread-safe repository for experiences and extracted knowledge."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._experiences: List[Experience] = []
        self._knowledge: Dict[str, Knowledge] = {}
        self._setup_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"wins": 0.0, "trades": 0.0, "r_sum": 0.0})

    def record_experience(self, experience: Experience) -> None:
        """Store a new trade experience and update aggregate stats."""
        with self._lock:
            self._experiences.append(experience)
            
            stats = self._setup_stats[experience.setup_name]
            stats["trades"] += 1.0
            if experience.win:
                stats["wins"] += 1.0
            stats["r_sum"] += experience.r_multiple

    def add_knowledge(self, knowledge: Knowledge) -> None:
        """Store extracted knowledge/rule."""
        with self._lock:
            self._knowledge[knowledge.knowledge_id] = knowledge

    def get_setup_stats(self, setup_name: str) -> dict[str, float]:
        """Get aggregate statistics for a specific setup."""
        with self._lock:
            stats = self._setup_stats.get(setup_name, {"wins": 0.0, "trades": 0.0, "r_sum": 0.0})
            return {
                "win_rate": (stats["wins"] + 1.0) / (stats["trades"] + 2.0),  # Beta-Binomial smoothing
                "expectancy": stats["r_sum"] / stats["trades"] if stats["trades"] > 0 else 0.0,
                "sample_size": stats["trades"]
            }

    def get_recent_experiences(self, limit: int = 100) -> List[Experience]:
        """Get recent experiences for analysis."""
        with self._lock:
            return list(self._experiences[-limit:])

    def get_all_knowledge(self) -> List[Knowledge]:
        """Retrieve all extracted knowledge rules."""
        with self._lock:
            return list(self._knowledge.values())

```

### File: `src/apex/research/research_engine.py`
```python
"""Research Engine - Extracts knowledge and updates Probability Engine."""
from __future__ import annotations

import uuid
import logging
from typing import Any

from .knowledge_base import KnowledgeBase
from ..domain.knowledge import Experience, Knowledge
from ..domain.trading import Trade
from ..engines.probability_engine import ProbabilityEngine

log = logging.getLogger(__name__)

class ResearchEngine:
    """Analyzes trade outcomes and feeds learning back into the system."""

    def __init__(self, knowledge_base: KnowledgeBase, prob_engine: ProbabilityEngine) -> None:
        self.kb = knowledge_base
        self.prob_engine = prob_engine
        self._trade_context_map: dict[str, Experience] = {}  # Maps trade_id to context

    def record_trade_context(self, trade_id: str, experience: Experience) -> None:
        """Temporarily store context when a trade opens, to be used when it closes."""
        self._trade_context_map[trade_id] = experience

    def process_closed_trade(self, trade: Trade) -> None:
        """Process a closed trade: Record experience, update Bayesian models."""
        # اصلاح: استفاده از position_id به جای trade_id
        experience = self._trade_context_map.pop(trade.position_id, None)
        
        if experience is None:
            log.warning(f"No context found for closed trade {trade.position_id}")
            return
            
        full_experience = Experience(
            trade_id=experience.trade_id,
            symbol=experience.symbol,
            setup_name=experience.setup_name,
            direction=experience.direction,
            win=trade.win,
            r_multiple=trade.r_multiple,
            probability_at_entry=experience.probability_at_entry,
            uncertainty_at_entry=experience.uncertainty_at_entry,
            regime=experience.regime,
            feature_vector=experience.feature_vector
        )
        
        self.kb.record_experience(full_experience)
        log.info(f"Recorded experience for {trade.symbol} {full_experience.setup_name}. Win: {trade.win}, R: {trade.r_multiple:.2f}")
        
        self.prob_engine.update_calibration(full_experience.probability_at_entry, full_experience.win)
        self.prob_engine.update_setup(full_experience.setup_name, full_experience.win, full_experience.r_multiple)
        
        self._extract_knowledge(full_experience.setup_name)

    def _extract_knowledge(self, setup_name: str) -> None:
        """Analyze setup statistics and extract knowledge if an edge is found."""
        stats = self.kb.get_setup_stats(setup_name)
        
        if stats["sample_size"] < 30:
            return
            
        win_rate = stats["win_rate"]
        expectancy = stats["expectancy"]
        
        if win_rate > 0.55 and expectancy > 0.2:
            knowledge = Knowledge(
                knowledge_id=f"KNW_{setup_name}_EDGE_{int(stats['sample_size'])}",
                category="setup_performance",
                description=f"Setup '{setup_name}' shows statistical edge with {win_rate*100:.1f}% win rate over {int(stats['sample_size'])} trades.",
                confidence=min(1.0, (win_rate - 0.5) * 2.0 * (stats["sample_size"] / 100.0)),
                sample_size=int(stats["sample_size"]),
                evidence=stats
            )
            self.kb.add_knowledge(knowledge)
            log.info(f"Knowledge Extracted: {knowledge.description}")
            
        elif win_rate < 0.45 and expectancy < -0.2:
            knowledge = Knowledge(
                knowledge_id=f"KNW_{setup_name}_FLAW_{int(stats['sample_size'])}",
                category="setup_flaw",
                description=f"Setup '{setup_name}' shows negative edge with {win_rate*100:.1f}% win rate. Consider disabling or re-optimizing.",
                confidence=min(1.0, (0.5 - win_rate) * 2.0 * (stats["sample_size"] / 100.0)),
                sample_size=int(stats["sample_size"]),
                evidence=stats
            )
            self.kb.add_knowledge(knowledge)
            log.warning(f"Knowledge Extracted (Warning): {knowledge.description}")

```

### File: `src/apex/security/__init__.py`
```python

```

### File: `tests/__init__.py`
```python

```

### File: `tests/test_core_foundation.py`
```python
"""Tests for core foundation - Phase 1."""
import pytest
import asyncio
from decimal import Decimal
from apex.core.types.primitives import Price, Probability
from apex.core.events import EventBus, Event
from apex.core.types.enums import EventType

def test_price_immutability_and_validation():
    with pytest.raises(ValueError):
        Price(Decimal("-100"))
    
    p1 = Price(Decimal("100.50"))
    p2 = Price(Decimal("50.25"))
    result = p1 + p2
    assert result.value == Decimal("150.75")

def test_probability_bounds():
    with pytest.raises(ValueError):
        Probability(1.5)
    
    prob = Probability(0.8)
    # استفاده از approx برای حل مشکل دقت اعشاری
    assert prob.complement().value == pytest.approx(0.2)

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
        
    bus.subscribe(EventType.NEW_TICK, handler)
    
    event = Event(event_type=EventType.NEW_TICK, payload={"data": 1})
    await bus.publish(event)
    
    assert len(received_events) == 1
    assert received_events[0].payload["data"] == 1

```

### File: `tests/test_data_platform.py`
```python
"""Tests for Data Platform - Phase 2."""
import pytest
import math
from apex.domain.market import MarketBar, Tick, OrderBook, OrderBookLevel
from apex.infrastructure.data_validator import DataValidator

def test_market_bar_validation_logic():
    bar = MarketBar(timestamp=1, open=100, high=110, low=90, close=105, volume=10)
    assert bar.range == 20
    assert bar.body == 5
    
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=100, high=90, low=110, close=100)
        
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=100, high=100, low=90, close=110)

def test_market_bar_nan_rejection():
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=math.nan, high=110, low=90, close=105)

def test_orderbook_properties():
    bids = (OrderBookLevel(price=99.0, quantity=1.0),)
    asks = (OrderBookLevel(price=101.0, quantity=1.0),)
    book = OrderBook(timestamp=1, symbol="BTC", bids=bids, asks=asks)
    
    assert book.best_bid == 99.0
    assert book.best_ask == 101.0
    assert book.mid_price == 100.0
    assert book.spread == 2.0
    # 2.0 / 100.0 * 10000 = 200.0 bps
    assert book.spread_bps == 200.0

def test_data_validator_tick():
    validator = DataValidator()
    tick = Tick(timestamp=1, price=100, volume=1, side="buy")
    res = validator.validate_tick(tick)
    assert res.is_valid
    
    # Domain object itself should reject invalid side before validator
    with pytest.raises(ValueError):
        Tick(timestamp=1, price=100, volume=1, side="unknown")

def test_data_validator_crossed_orderbook():
    validator = DataValidator()
    bids = (OrderBookLevel(price=101.0, quantity=1.0),) # Bid > Ask
    asks = (OrderBookLevel(price=100.0, quantity=1.0),)
    book = OrderBook(timestamp=1, symbol="BTC", bids=bids, asks=asks)
    
    res = validator.validate_orderbook(book)
    assert not res.is_valid
    assert "Crossed orderbook" in res.errors[0]

```

### File: `tests/test_decision_engine.py`
```python
"""Tests for Decision Engine - Phase 5."""
import pytest
from apex.domain.contracts import ProbabilityReport
from apex.domain.trading import PortfolioState, Decision
from apex.engines.decision_engine import DecisionEngine
from apex.engines.governance import GovernanceEngine, GovernancePolicy

@pytest.fixture
def engine():
    policy = GovernancePolicy(
        max_concurrent_trades=5, min_probability_threshold=0.62, min_prob_edge=0.03,
        min_contributors=3, min_expected_r=0.10, max_uncertainty=0.45, min_decision_readiness=0.40
    )
    return DecisionEngine(GovernanceEngine(policy))

def test_decision_kill_switch(engine):
    prob = ProbabilityReport(probability_long=0.9, probability_short=0.05, probability_neutral=0.05)
    portfolio = PortfolioState(health_score=0.1)  # Critical health
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "NO_TRADE"
    assert "Kill switch active" in decision.reasoning

def test_decision_portfolio_limits(engine):
    prob = ProbabilityReport(probability_long=0.9, probability_short=0.05, probability_neutral=0.05)
    portfolio = PortfolioState(open_positions_count=5)  # Max reached
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "NO_TRADE"
    assert "Max concurrent trades reached" in decision.reasoning[0]

def test_decision_low_dri(engine):
    prob = ProbabilityReport(
        probability_long=0.9, probability_short=0.05, probability_neutral=0.05,
        uncertainty=0.2, decision_readiness_index=0.20  # Low DRI
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5)
    
    assert decision.decision_type == "WAIT"
    assert "DRI too low" in decision.reasoning[0]

def test_decision_trade_approved(engine):
    prob = ProbabilityReport(
        probability_long=0.85, probability_short=0.10, probability_neutral=0.05,
        confidence=0.7, uncertainty=0.2, expected_r=0.5,
        decision_readiness_index=0.8
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=5, contributors_short=2)
    
    assert decision.decision_type == "TRADE"
    assert decision.direction == "LONG"
    assert decision.confidence > 0.0
    assert "All gates passed" in decision.reasoning[0]

def test_decision_rejected_low_contributors(engine):
    prob = ProbabilityReport(
        probability_long=0.85, probability_short=0.10, probability_neutral=0.05,
        uncertainty=0.2, expected_r=0.5, decision_readiness_index=0.8
    )
    portfolio = PortfolioState()
    
    decision = engine.evaluate(prob, portfolio, contributors_long=2)  # < 3
    
    assert decision.decision_type == "NO_TRADE"
    assert "Insufficient long contributors" in decision.reasoning[-1]

```

### File: `tests/test_execution_engine.py`
```python
"""Tests for Execution Engine - Phase 8."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from apex.engines.execution_engine import ExecutionEngine
from apex.infrastructure.exchanges.toobit_adapter import ToobitAdapter
from apex.domain.trading import TradeBlueprint

@pytest.fixture
def blueprint():
    return TradeBlueprint(
        decision_id="test_123", symbol="BTC-SWAP-USDT", exchange="toobit", direction="LONG",
        probability=0.8, confidence=0.7, expected_value=0.5, position_size=10.0, risk_size=100.0,
        entry_price=50000.0, stop_loss=49000.0, take_profit=52000.0, tp1=51000.0, tp2=51500.0, tp3=52000.0
    )

@pytest.mark.asyncio
async def test_toobit_adapter_direction_mapping(blueprint):
    adapter = ToobitAdapter("key", "secret")
    assert adapter._map_direction_to_side("LONG") == "BUY_OPEN"
    assert adapter._map_direction_to_side("SHORT") == "SELL_OPEN"
    
    with pytest.raises(ValueError):
        adapter._map_direction_to_side("FLAT")

@pytest.mark.asyncio
async def test_execution_engine_success(blueprint):
    # Mock the adapter
    mock_adapter = MagicMock()
    mock_response = {"orderId": "toobit_123", "status": "NEW"}
    mock_adapter.place_order = AsyncMock(return_value=mock_response)
    
    engine = ExecutionEngine(mock_adapter)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "NEW"
    assert response["orderId"] == "toobit_123"
    mock_adapter.place_order.assert_called_once()

@pytest.mark.asyncio
async def test_execution_engine_retry_on_rate_limit(blueprint):
    mock_adapter = MagicMock()
    
    rejected_response = {"code": -1015, "msg": "Too many orders", "status": "REJECTED"}
    accepted_response = {"orderId": "toobit_456", "status": "NEW"}
    
    # First call rejects, second accepts
    mock_adapter.place_order = AsyncMock(side_effect=[rejected_response, accepted_response])
    
    engine = ExecutionEngine(mock_adapter, max_retries=3)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "NEW"
    assert mock_adapter.place_order.call_count == 2

@pytest.mark.asyncio
async def test_execution_engine_permanent_rejection(blueprint):
    mock_adapter = MagicMock()
    
    rejected_response = {"code": -1131, "msg": "Balance insufficient", "status": "REJECTED"}
    mock_adapter.place_order = AsyncMock(return_value=rejected_response)
    
    engine = ExecutionEngine(mock_adapter, max_retries=3)
    response = await engine.execute_blueprint(blueprint)
    
    assert response["status"] == "REJECTED"
    # Should not retry on -1131
    mock_adapter.place_order.assert_called_once()

```

### File: `tests/test_feature_platform.py`
```python
"""Tests for Feature Platform - Phase 3."""
import pytest
import math
from apex.features.feature_store import FeatureStore, Feature, FeatureCategory
from apex.features.primitives import PrimitiveFeatures
from apex.domain.market import MarketBar

@pytest.fixture
def sample_bars():
    bars = []
    price = 100.0
    for i in range(20):
        bars.append(MarketBar(
            timestamp=float(i),
            open=price,
            high=price + (i % 3) + 1,
            low=price - (i % 2) - 1,
            close=price + (i % 2),
            volume=10.0 * (i + 1)
        ))
        price += 0.5
    return bars

def test_feature_store_dependency_graph():
    store = FeatureStore()
    store.register("RSI", FeatureCategory.MOMENTUM, dependencies=[])
    store.register("RSI_SMA", FeatureCategory.MOMENTUM, dependencies=["RSI"])
    
    assert not store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=10.0)
    
    # اصلاح: افزودن symbol و timeframe به فیچر
    rsi_feat = Feature(feature_id="1", name="RSI", category=FeatureCategory.MOMENTUM, timestamp=10.0, symbol="BTC", timeframe="1m")
    store.store(rsi_feat)
    
    assert store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=10.0)
    assert not store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=100.0, max_age_sec=10.0)

def test_primitive_features_atr(sample_bars):
    store = FeatureStore()
    engine = PrimitiveFeatures(store)
    
    atr = engine.calculate_atr(sample_bars, period=14, symbol="BTC", timeframe="1m")
    
    assert atr.name == "ATR"
    assert atr.value > 0
    assert atr.confidence == 1.0
    assert not math.isnan(atr.value)
    
    retrieved = store.get("ATR", "BTC", "1m")
    assert retrieved is not None
    assert retrieved.value == atr.value

def test_primitive_features_rsi_division_by_zero():
    store = FeatureStore()
    engine = PrimitiveFeatures(store)
    
    flat_bars = [
        MarketBar(timestamp=float(i), open=100, high=100, low=100, close=100)
        for i in range(20)
    ]
    
    rsi = engine.calculate_rsi(flat_bars, period=14, symbol="ETH", timeframe="1m")
    
    assert rsi.value == 50.0
    assert rsi.confidence == 1.0

def test_feature_immutability_and_nan_rejection():
    with pytest.raises(ValueError):
        Feature(
            feature_id="1",
            name="TEST",
            category=FeatureCategory.PRICE,
            value=float('nan')
        )

```

### File: `tests/test_integration.py`
```python
"""Integration test for the full APEX pipeline - Phase 12."""
import pytest
import asyncio
import math
from unittest.mock import AsyncMock, MagicMock

from apex.application.bootstrap import Application
from apex.core.events import EventBus, Event
from apex.core.types.enums import EventType
from apex.domain.market import MarketBar

@pytest.fixture
def app():
    # We test the internal pipeline without real WS connection
    return Application(api_key="test", api_secret="test", symbols=["BTC-SWAP-USDT"])

@pytest.mark.asyncio
async def test_full_trade_cycle_with_sl_tp(app):
    await app.initialize()
    
    # 1. Generate 25 bearish bars (RSI < 40) to trigger LONG signal in our simple logic
    base_price = 50000.0
    for i in range(25):
        price = base_price - (i * 50)
        bar = MarketBar(
            timestamp=float(i),
            open=price + 25,
            high=price + 50,
            low=price - 50,
            close=price,
            volume=100.0,
            symbol="BTC-SWAP-USDT",
            timeframe="1m"
        )
        # Simulate WS event
        event = Event(event_type=EventType.NEW_CANDLE, source="test", payload={"bar": bar.__dict__})
        
        # Mock the execution engine to avoid real API calls
        app.execution_engine.execute_blueprint = AsyncMock(return_value={"orderId": "mock_123", "status": "NEW"})
        
        await app._on_new_candle(event)
        
    # Check if position was opened
    assert len(app.portfolio_engine.open_positions) > 0
    position = list(app.portfolio_engine.open_positions.values())[0]
    assert position.direction == "LONG"
    assert position.stop_loss < position.entry_price
    assert position.take_profit > position.entry_price
    
    # 2. Simulate price hitting Take Profit
    tp_price = position.take_profit
    tick_event = Event(
        event_type=EventType.NEW_TICK, 
        source="test", 
        payload={"tick": {"symbol": "BTC-SWAP-USDT", "price": tp_price}}
    )
    await app._on_new_tick(tick_event)
    
    # 3. Verify position closed and learning occurred
    assert len(app.portfolio_engine.open_positions) == 0
    assert len(app.portfolio_engine.closed_trades) == 1
    trade = app.portfolio_engine.closed_trades[0]
    assert trade.win == True
    
    # Verify Research Engine learned
    stats = app.knowledge_base.get_setup_stats("IntegrationTest")
    assert stats["sample_size"] == 1
    assert stats["win_rate"] > 0.5  # Beta-Binomial smoothing (1+1)/(1+2) = 0.66

```

### File: `tests/test_market_data_ws.py`
```python
"""Tests for Toobit WebSocket Client - Phase 9."""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from apex.infrastructure.exchanges.toobit_ws import ToobitWebSocketClient
from apex.core.events import EventBus
from apex.core.types.enums import EventType

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def ws_client(event_bus):
    return ToobitWebSocketClient(event_bus, ["BTC-SWAP-USDT"])

@pytest.mark.asyncio
async def test_process_trade_message(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_TICK, handler)
    
    mock_msg = {
        "symbol": "BTC-SWAP-USDT",
        "topic": "trade",
        "data": [
            {
                "v": "1291465821801168896",
                "t": 1668690723096,
                "p": "399",
                "q": "1.5",
                "m": False  # False means Buy side
            }
        ]
    }
    
    await ws_client._process_message(mock_msg)
    
    assert len(received_events) == 1
    tick_data = received_events[0].payload["tick"]
    assert tick_data["symbol"] == "BTC-SWAP-USDT"
    assert tick_data["price"] == 399.0
    assert tick_data["volume"] == 1.5
    assert tick_data["side"] == "buy"

@pytest.mark.asyncio
async def test_process_kline_message(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_CANDLE, handler)
    
    mock_msg = {
        "symbol": "BTC-SWAP-USDT",
        "topic": "kline",
        "params": {"klineType": "1m"},
        "data": [
            {
                "t": 1668753840000,
                "s": "BTC-SWAP-USDT",
                "c": "445.5",
                "h": "446.0",
                "l": "444.0",
                "o": "444.2",
                "v": "10.5"
            }
        ]
    }
    
    await ws_client._process_message(mock_msg)
    
    assert len(received_events) == 1
    bar_data = received_events[0].payload["bar"]
    assert bar_data["symbol"] == "BTC-SWAP-USDT"
    assert bar_data["open"] == 444.2
    assert bar_data["high"] == 446.0
    assert bar_data["close"] == 445.5
    assert bar_data["volume"] == 10.5
    assert bar_data["timeframe"] == "1m"

@pytest.mark.asyncio
async def test_pong_message_ignored(ws_client, event_bus):
    received_events = []
    
    async def handler(event):
        received_events.append(event)
        
    event_bus.subscribe(EventType.NEW_TICK, handler)
    event_bus.subscribe(EventType.NEW_CANDLE, handler)
    
    mock_pong = {"pong": 1535975085052}
    await ws_client._process_message(mock_pong)
    
    assert len(received_events) == 0

@pytest.mark.asyncio
async def test_heartbeat_sends_ping(ws_client):
    ws_client._running = True  # <--- اصلاح این خط
    ws_client._ws = MagicMock()
    ws_client._ws.closed = False
    ws_client._ws.send = AsyncMock()
    
    task = asyncio.create_task(ws_client._heartbeat_loop())
    await asyncio.sleep(0.1)  # Allow it to execute
    task.cancel()
    
    ws_client._ws.send.assert_called_once()
    sent_msg = json.loads(ws_client._ws.send.call_args[0][0])
    assert "ping" in sent_msg

```

### File: `tests/test_observability.py`
```python
"""Tests for Observability Platform - Phase 11."""
import pytest
import json
import time
from apex.monitoring.structured_logger import StructuredLogger
from apex.monitoring.metrics_engine import MetricsEngine
from apex.monitoring.health_monitor import HealthMonitor
from apex.monitoring.contracts import Metric, HealthReport

def test_structured_logger_outputs_json(capsys):
    logger = StructuredLogger("TestModule")
    logger.info("Trade executed", trade_id="123", pnl=50.5)
    
    captured = capsys.readouterr()
    log_dict = json.loads(captured.out.strip())
    
    assert log_dict["module"] == "TestModule"
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Trade executed"
    assert log_dict["trade_id"] == "123"
    assert log_dict["pnl"] == 50.5

def test_metrics_engine_record_and_retrieve():
    engine = MetricsEngine()
    engine.record("cpu_usage", 45.5, "%", node="main")
    engine.record("cpu_usage", 55.0, "%", node="main")
    
    latest = engine.get_latest("cpu_usage")
    assert latest is not None
    assert latest.value == 55.0
    assert latest.tags["node"] == "main"
    
    history = engine.get_history("cpu_usage")
    assert len(history) == 2

def test_metrics_engine_nan_rejection():
    engine = MetricsEngine()
    with pytest.raises(ValueError):
        engine.record("invalid_metric", float('nan'))

def test_health_monitor_heartbeat_and_timeout():
    monitor = HealthMonitor(heartbeat_timeout=0.1)  # 100ms timeout
    monitor.register_module("ExecutionEngine")
    monitor.heartbeat("ExecutionEngine")
    
    statuses = monitor.get_all_statuses()
    assert statuses["ExecutionEngine"].status == "HEALTHY"
    
    time.sleep(0.2)
    statuses = monitor.get_all_statuses()
    assert statuses["ExecutionEngine"].status == "OFFLINE"
    assert statuses["ExecutionEngine"].score == 0.0

def test_health_monitor_manual_score_update():
    monitor = HealthMonitor()
    monitor.register_module("ProbabilityEngine")
    # 0.6 is between 0.5 and 0.8, so it should be WARNING
    monitor.update_status("ProbabilityEngine", 0.6, {"reason": "High uncertainty"})
    
    statuses = monitor.get_all_statuses()
    assert statuses["ProbabilityEngine"].status == "WARNING"
    assert statuses["ProbabilityEngine"].score == 0.6

```

### File: `tests/test_portfolio_engine.py`
```python
"""Tests for Portfolio Engine - Phase 7."""
import pytest
import math
from apex.engines.portfolio_engine import PortfolioEngine
from apex.domain.trading import Position

@pytest.fixture
def engine():
    return PortfolioEngine(initial_capital=10000.0, max_drawdown=0.10)

@pytest.fixture
def long_position():
    return Position(
        position_id="pos_1", blueprint_id="bp_1", symbol="BTCUSDT", exchange="toobit",
        direction="LONG", entry_price=100.0, quantity=10.0, stop_loss=90.0, take_profit=120.0
    )

def test_portfolio_initial_state(engine):
    state = engine.get_state()
    assert state.total_equity == 10000.0
    assert state.drawdown == 0.0
    assert state.health_score == 1.0
    assert state.open_positions_count == 0

def test_portfolio_add_position_and_pnl(engine, long_position):
    engine.add_position(long_position)
    assert engine.get_state().open_positions_count == 1
    engine.update_positions({"BTCUSDT": 110.0})
    state = engine.get_state()
    assert math.isclose(state.total_equity, 10100.0)
    assert state.drawdown == 0.0
    engine.update_positions({"BTCUSDT": 95.0})
    state = engine.get_state()
    assert math.isclose(state.total_equity, 9950.0)
    assert state.drawdown > 0.0

def test_portfolio_close_position(engine, long_position):
    engine.add_position(long_position)
    engine.update_positions({"BTCUSDT": 110.0})
    trade = engine.close_position("pos_1", 110.0)
    assert trade is not None
    assert trade.win
    assert math.isclose(trade.pnl, 100.0)
    assert math.isclose(trade.r_multiple, 1.0)
    state = engine.get_state()
    assert state.open_positions_count == 0
    assert math.isclose(state.total_equity, 10100.0)

def test_portfolio_kill_switch(engine, long_position):
    large_pos = Position(
        position_id="pos_2", blueprint_id="bp_2", symbol="BTCUSDT", exchange="toobit",
        direction="LONG", entry_price=100.0, quantity=100.0, stop_loss=80.0, take_profit=150.0
    )
    engine.add_position(large_pos)
    engine.update_positions({"BTCUSDT": 99.0})
    assert not engine.kill_switch_active
    engine.update_positions({"BTCUSDT": 89.0})
    assert engine.kill_switch_active
    assert engine.get_state().health_score < 0.1
    assert not engine.add_position(long_position)

```

### File: `tests/test_probability_engine.py`
```python
"""Tests for Probability Engine - Phase 4."""
import pytest
import math
from apex.engines.probability_engine import ProbabilityEngine, BayesianModel
from apex.domain.contracts import ProbabilityReport

def test_bayesian_model_posterior_and_update():
    model = BayesianModel(alpha=6.0, beta=6.0)
    assert 0.4 < model.posterior < 0.6
    
    # Test Win
    model.update(score=0.9, win=True, r=2.0)
    assert model.alpha > 6.0
    assert model.beta == 6.0
    assert model.posterior > 0.5
    
    # Test Loss in isolation to check expected_r logic
    loss_model = BayesianModel(alpha=6.0, beta=6.0)
    loss_model.update(score=0.8, win=False, r=-1.0)
    assert loss_model.beta > 6.0
    assert loss_model.expected_r < 0

def test_probability_engine_calibrate():
    engine = ProbabilityEngine()
    
    calibrated_low = engine.calibrate(0.2)
    assert 0.1 < calibrated_low < 0.3
    
    # Inject bias into bin 8 (0.8 probability)
    for _ in range(50):
        engine.update_calibration(0.8, win=True)
        
    # Read calibration from the same bin (0.8)
    calibrated_high = engine.calibrate(0.8)
    assert calibrated_high > 0.8

def test_probability_engine_compute_distribution_sums_to_1():
    engine = ProbabilityEngine()
    evidence_long = {"structure": 0.7, "liquidity": 0.6, "trend": 0.5}
    evidence_short = {"structure": 0.2, "liquidity": 0.3, "trend": 0.4}
    weights = {"structure": 0.3, "liquidity": 0.4, "trend": 0.3}

    report = engine.compute_probability(evidence_long, evidence_short, weights)

    assert isinstance(report, ProbabilityReport)
    total_prob = report.probability_long + report.probability_short + report.probability_neutral
    assert math.isclose(total_prob, 1.0, abs_tol=1e-6)
    
    assert report.probability_long > report.probability_short
    assert report.consensus > 0.0

def test_probability_engine_uncertainty_and_attribution():
    engine = ProbabilityEngine()
    
    evidence_long = {"structure": 0.9, "liquidity": 0.9}
    evidence_short = {"structure": 0.8, "liquidity": 0.8}
    weights = {"structure": 0.5, "liquidity": 0.5}
    
    report = engine.compute_probability(evidence_long, evidence_short, weights)
    assert report.uncertainty > 0.5
    
    assert report.feature_attribution["structure"] > 0
    assert report.feature_attribution["liquidity"] > 0

def test_probability_report_nan_rejection():
    with pytest.raises(ValueError):
        ProbabilityReport(probability_long=float('nan'), probability_short=0.5, probability_neutral=0.5)

```

### File: `tests/test_research_engine.py`
```python
"""Tests for Research Engine - Phase 10."""
import pytest
from apex.research.knowledge_base import KnowledgeBase
from apex.research.research_engine import ResearchEngine
from apex.engines.probability_engine import ProbabilityEngine
from apex.domain.trading import Trade
from apex.domain.knowledge import Experience

@pytest.fixture
def setup():
    kb = KnowledgeBase()
    pe = ProbabilityEngine()
    engine = ResearchEngine(kb, pe)
    return kb, pe, engine

def test_knowledge_base_record_and_stats(setup):
    kb, _, _ = setup
    
    exp1 = Experience("t1", "BTC", "Turtle Soup", "LONG", True, 2.0, 0.8, 0.2, "neutral")
    exp2 = Experience("t2", "BTC", "Turtle Soup", "LONG", False, -1.0, 0.7, 0.3, "neutral")
    
    kb.record_experience(exp1)
    kb.record_experience(exp2)
    
    stats = kb.get_setup_stats("Turtle Soup")
    assert stats["sample_size"] == 2
    assert stats["win_rate"] == 0.5
    assert stats["expectancy"] == 0.5

def test_research_engine_feedback_loop(setup):
    kb, pe, engine = setup
    
    # ثبت زمینه با position_id (مطابق کد واقعی bootstrap.py)
    context = Experience("t100", "ETH", "FVG Continuation", "LONG", False, 0.0, 0.85, 0.2, "neutral")
    engine.record_trade_context("p100", context)
    
    assert pe.calibration_bins[8].trades == 0.0
    
    closed_trade = Trade(
        trade_id="t100", position_id="p100", symbol="ETH", direction="LONG",
        entry_price=100, exit_price=110, quantity=1, pnl=10, r_multiple=1.5, win=True
    )
    
    engine.process_closed_trade(closed_trade)
    
    assert pe.calibration_bins[8].trades == 1.0
    assert pe.calibration_bins[8].wins == 1.0
    
    stats = kb.get_setup_stats("FVG Continuation")
    assert stats["sample_size"] == 1

def test_knowledge_extraction_positive_edge(setup):
    kb, pe, engine = setup
    
    for i in range(35):
        exp = Experience(f"t{i}", "BTC", "Super Setup", "LONG", True, 2.0, 0.8, 0.2, "neutral")
        # ثبت زمینه با position_id (مطابق کد واقعی bootstrap.py)
        engine.record_trade_context(f"p{i}", exp)
        trade = Trade(
            trade_id=f"t{i}", position_id=f"p{i}", symbol="BTC", direction="LONG",
            entry_price=100, exit_price=120, quantity=1, pnl=20, r_multiple=2.0, win=True
        )
        engine.process_closed_trade(trade)
        
    knowledge_list = kb.get_all_knowledge()
    assert len(knowledge_list) > 0
    
    edge_knowledge = knowledge_list[0]
    assert edge_knowledge.category == "setup_performance"
    assert "Super Setup" in edge_knowledge.description
    assert edge_knowledge.confidence > 0.0

```

### File: `tests/test_risk_engine.py`
```python
"""Tests for Risk Engine - Phase 6."""
import pytest
import math
from apex.engines.risk_engine import RiskEngine
from apex.domain.trading import PortfolioState, Decision
from apex.domain.contracts import ProbabilityReport

@pytest.fixture
def engine():
    return RiskEngine(risk_per_trade_pct=1.0, sl_mult=2.0, tp_mult=3.5)

@pytest.fixture
def portfolio():
    return PortfolioState(total_equity=10000.0, available_capital=10000.0)

@pytest.fixture
def long_decision():
    return Decision(decision_type="TRADE", direction="LONG", confidence=0.8, trace_id="test_long")

@pytest.fixture
def prob_report():
    return ProbabilityReport(probability_long=0.8, probability_short=0.1, probability_neutral=0.1)

def test_stop_loss_atr_only(engine):
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG")
    assert math.isclose(sl, 90.0)
    
    sl = engine.compute_stop_loss(100.0, 5.0, "SHORT")
    assert math.isclose(sl, 110.0)

def test_stop_loss_structure_hybrid(engine):
    # OB Bot at 92, ATR 5. Struct SL = 92 - 0.75 = 91.25
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG", ob_bot=92.0)
    assert math.isclose(sl, 91.25)
    
    # If OB Bot is too far, fallback to ATR
    sl = engine.compute_stop_loss(100.0, 5.0, "LONG", ob_bot=50.0)
    assert math.isclose(sl, 90.0)

def test_take_profit_liquidity_targets(engine):
    # Risk=10, Base RR=1.75. TP3 Cand = 126.25
    tp1, tp2, tp3, tp = engine.compute_take_profit(100.0, 90.0, "LONG")
    assert math.isclose(tp1, 108.75)
    assert math.isclose(tp2, 117.5)
    assert math.isclose(tp3, 126.25)
    
    # With HTF High at 120.0 -> TP3 should be 120.0
    tp1, tp2, tp3, tp = engine.compute_take_profit(100.0, 90.0, "LONG", htf_high=120.0)
    assert math.isclose(tp3, 120.0)

def test_position_sizing(engine, portfolio):
    # Risk 1% of 10000 = 100. Risk per unit = 10. Size = 10
    size, risk = engine.compute_position_size(10000.0, 100.0, 90.0)
    assert math.isclose(size, 10.0)
    assert math.isclose(risk, 100.0)

def test_create_blueprint_long(engine, portfolio, long_decision, prob_report):
    blueprint = engine.create_blueprint(
        decision=long_decision,
        portfolio=portfolio,
        probability_report=prob_report,
        current_price=100.0,
        atr=5.0,
        ob_bot=92.0,
        htf_high=120.0
    )
    
    assert blueprint is not None
    assert blueprint.direction == "LONG"
    assert blueprint.entry_price == 100.0
    assert math.isclose(blueprint.stop_loss, 91.25)
    assert math.isclose(blueprint.take_profit, 120.0)
    assert blueprint.position_size > 0
    assert 0.0 <= blueprint.trade_quality_index <= 1.0

```
