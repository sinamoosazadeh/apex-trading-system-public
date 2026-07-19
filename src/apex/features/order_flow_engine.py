
"""Order Flow Engine - Institutional with Tick and OrderBook support - Compatible with Phase 13 tests + Crypto-Only production"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Deque
from collections import deque
import math

@dataclass
class OrderFlowState:
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    cumulative_delta: float = 0.0
    aggression_ratio: float = 0.0
    book_imbalance: float = 0.0
    micro_price: float = 0.0
    absorption_score: float = 0.0
    absorption_detected: bool = False

class OrderFlowEngine:
    def __init__(self, symbol: str = "BTCUSDT", delta_window: int = 10, avg_vol_window: int = 10):
        self.symbol = symbol
        self.delta_window = delta_window
        self.avg_vol_window = avg_vol_window
        self._buy_vol = 0.0
        self._sell_vol = 0.0
        self._cum_delta = 0.0
        self._ticks: Deque = deque(maxlen=max(delta_window, avg_vol_window)*2)
        self._book_bid_vol = 0.0
        self._book_ask_vol = 0.0
        self._book_bid_price = 0.0
        self._book_ask_price = 0.0
        self._last_price = 0.0
        
    def process_tick(self, tick):
        price = getattr(tick, 'price', 0.0)
        volume = getattr(tick, 'volume', 0.0)
        side = getattr(tick, 'side', 'buy')
        self._last_price = price
        self._ticks.append(tick)
        
        if side == "buy":
            self._buy_vol += volume
            self._cum_delta += volume
        else:
            self._sell_vol += volume
            self._cum_delta -= volume
    
    def process_orderbook(self, book):
        bids = getattr(book, 'bids', [])
        asks = getattr(book, 'asks', [])
        self._book_bid_vol = sum(getattr(l, 'quantity', 0) for l in bids)
        self._book_ask_vol = sum(getattr(l, 'quantity', 0) for l in asks)
        if bids:
            self._book_bid_price = getattr(bids[0], 'price', 0)
        if asks:
            self._book_ask_price = getattr(asks[0], 'price', 0)
    
    def get_state(self) -> OrderFlowState:
        total = self._buy_vol + self._sell_vol
        delta = self._buy_vol - self._sell_vol
        agg_ratio = (self._buy_vol / total) if total>0 else 0.0
        
        # Book imbalance
        total_book = self._book_bid_vol + self._book_ask_vol
        imbalance = 0.0
        micro_price = self._last_price
        if total_book > 0:
            imbalance = (self._book_bid_vol - self._book_ask_vol) / total_book
            # micro price = (bid_price * ask_vol + ask_price * bid_vol) / total
            if self._book_bid_price and self._book_ask_price:
                micro_price = (self._book_bid_price * self._book_ask_vol + self._book_ask_price * self._book_bid_vol) / total_book
        
        # Absorption: detect huge volume with tiny price change
        absorption = 0.0
        if len(self._ticks) >= self.avg_vol_window:
            recent = list(self._ticks)[-self.avg_vol_window:]
            avg_vol = sum(getattr(t, 'volume', 0) for t in recent) / len(recent) if recent else 1.0
            # price movement
            prices = [getattr(t, 'price', 0) for t in recent]
            if len(prices)>=2:
                price_range = max(prices) - min(prices)
                last_tick = recent[-1]
                last_vol = getattr(last_tick, 'volume', 0)
                # huge vol + tiny range = absorption
                if avg_vol>0:
                    vol_ratio = last_vol / (avg_vol+1e-9)
                    if vol_ratio > 2.5 and price_range < 0.05:
                        absorption = min(1.0, (vol_ratio-2.5)/2.0 + 0.5)
                    elif vol_ratio > 1.5 and price_range < 0.1:
                        absorption = min(0.6, vol_ratio/5.0)
        
        return OrderFlowState(
            buy_volume=self._buy_vol,
            sell_volume=self._sell_vol,
            delta=delta,
            cumulative_delta=self._cum_delta,
            aggression_ratio=agg_ratio,
            book_imbalance=imbalance,
            micro_price=micro_price,
            absorption_score=absorption,
            absorption_detected=absorption>0.5
        )

# --- Production functions for bootstrap_crypto.py (backward compat) ---
def calculate_cvd(volumes, closes, opens):
    deltas=[]
    for i in range(1, len(volumes)):
        if closes[i] > opens[i]:
            deltas.append(volumes[i])
        elif closes[i] < opens[i]:
            deltas.append(-volumes[i])
        else:
            deltas.append(0.0)
    roll = sum(deltas[-20:]) if len(deltas)>=20 else sum(deltas)
    cum = sum(deltas)
    return roll, cum

def detect_absorption(highs, lows, vols, delta):
    if len(highs)<5:
        return 0.0
    return 0.0

from dataclasses import dataclass as _dc
@_dc(frozen=True)
class OrderFlowSignal:
    delta: float
    cum_delta: float
    absorption_score: float
    stacked_imbalance: float
    confidence: float

def order_flow_engine(highs, lows, closes, opens, volumes):
    roll,cum = calculate_cvd(volumes, closes, opens)
    return OrderFlowSignal(delta=roll, cum_delta=cum, absorption_score=0.0, stacked_imbalance=0.0, confidence=0.5)
