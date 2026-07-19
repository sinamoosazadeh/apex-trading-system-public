"""Order Flow Intelligence Engine."""
from __future__ import annotations

import math
from collections import deque
from typing import Dict, Deque

from ..domain.market import Tick, OrderBook
from ..domain.flow import OrderFlowState
from .indicators import clamp

class OrderFlowEngine:
    """Processes live ticks and order book updates for flow analysis."""

    def __init__(self, symbol: str, delta_window: int = 50, avg_vol_window: int = 100) -> None:
        self.symbol = symbol
        self.delta_window = delta_window
        self.avg_vol_window = avg_vol_window
        
        self._ticks: Deque[Tick] = deque(maxlen=delta_window)
        self._volumes: Deque[float] = deque(maxlen=avg_vol_window)
        self._cumulative_delta: float = 0.0
        self._last_book: OrderBook | None = None
        self._last_price: float = 0.0

    def process_tick(self, tick: Tick) -> None:
        """Process a new tick and update flow metrics."""
        self._ticks.append(tick)
        self._volumes.append(tick.volume)
        
        if tick.side == 'buy':
            self._cumulative_delta += tick.volume
        else:
            self._cumulative_delta -= tick.volume
            
        self._last_price = tick.price

    def process_orderbook(self, book: OrderBook) -> None:
        """Process a new order book snapshot."""
        self._last_book = book

    def get_state(self) -> OrderFlowState:
        """Calculate and return the current order flow state."""
        if not self._ticks:
            return OrderFlowState(timestamp=0.0, symbol=self.symbol)

        # 1. Trade Flow Metrics
        buy_vol = sum(t.volume for t in self._ticks if t.side == 'buy')
        sell_vol = sum(t.volume for t in self._ticks if t.side == 'sell')
        total_vol = buy_vol + sell_vol
        
        delta = buy_vol - sell_vol
        aggression_ratio = delta / total_vol if total_vol > 0 else 0.0

        # 2. Order Book Metrics (Fallback to 0 if book not available yet)
        book_imbalance = 0.0
        micro_price = 0.0
        spread_bps = 0.0
        
        if self._last_book:
            bid_vol = self._last_book.bid_volume
            ask_vol = self._last_book.ask_volume
            total_book_vol = bid_vol + ask_vol
            
            book_imbalance = (bid_vol - ask_vol) / total_book_vol if total_book_vol > 0 else 0.0
            
            bb = self._last_book.best_bid
            ba = self._last_book.best_ask
            micro_price = (bb * ask_vol + ba * bid_vol) / total_book_vol if total_book_vol > 0 else (bb + ba) / 2.0
            spread_bps = self._last_book.spread_bps

        # 3. Absorption & Exhaustion Detection
        avg_vol = sum(self._volumes) / len(self._volumes) if self._volumes else 1.0
        current_vol = self._ticks[-1].volume if self._ticks else 0.0
        vol_spike = current_vol > (avg_vol * 2.0) if avg_vol > 0 else False
        
        price_change = 0.0
        if len(self._ticks) >= 2:
            price_change = abs(self._ticks[-1].price - self._ticks[-2].price)
            
        absorption_score = 0.0
        if vol_spike and current_vol > 0:
            expected_move = current_vol / max(avg_vol, 1.0) * 0.01
            if price_change < expected_move:
                absorption_score = clamp(1.0 - (price_change / max(expected_move, 0.0001)), 0.0, 1.0)

        exhaustion_score = clamp(absorption_score * 0.8, 0.0, 1.0)

        return OrderFlowState(
            timestamp=self._ticks[-1].timestamp if self._ticks else 0.0,
            symbol=self.symbol,
            delta=delta,
            cumulative_delta=self._cumulative_delta,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            aggression_ratio=clamp(aggression_ratio, -1.0, 1.0),
            book_imbalance=clamp(book_imbalance, -1.0, 1.0),
            micro_price=micro_price,
            spread_bps=spread_bps,
            absorption_score=absorption_score,
            exhaustion_score=exhaustion_score
        )
