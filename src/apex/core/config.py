
"""Core Config - Full Institutional - Crypto-Only"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class ToobitConfig:
    api_key: str = field(default_factory=lambda: os.getenv("TOOBIT_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("TOOBIT_API_SECRET", ""))
    base_url: str = "https://api.toobit.com"
    ws_url: str = "wss://stream.toobit.com/quote/ws/v1"
    testnet: bool = False

@dataclass
class TradingConfig:
    symbols: List[str] = field(default_factory=lambda: [
        "BTC-SWAP-USDT", "ETH-SWAP-USDT", "SOL-SWAP-USDT", "XRP-SWAP-USDT", "BNB-SWAP-USDT",
        "DOGE-SWAP-USDT", "ADA-SWAP-USDT", "AVAX-SWAP-USDT", "LINK-SWAP-USDT", "DOT-SWAP-USDT"
    ])
    timeframes: List[str] = field(default_factory=lambda: [
        "1m","3m","5m","15m","30m","1h","2h","4h","6h","12h","1d","3d","1w","1M"
    ])
    initial_capital: float = 10000.0
    risk_per_trade: float = 0.01
    max_positions: int = 3
    mode_24_7: bool = True  # Crypto-only, no forex sessions

@dataclass
class RiskConfig:
    atr_sl_multiplier: float = 1.5
    atr_tp_multiplier: float = 3.0
    max_drawdown: float = 0.15
    kill_switch_enabled: bool = True

@dataclass
class BacktestConfig:
    full_history: bool = True  # Per blueprint - all candles
    display_last_n_signals: int = 25  # Per user request
    commission: float = 0.0004
    slippage: float = 0.0002

@dataclass
class ApexConfig:
    toobit: ToobitConfig = field(default_factory=ToobitConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    env: str = field(default_factory=lambda: os.getenv("APEX_ENV", "production"))
    log_level: str = "INFO"
    
    def validate(self):
        assert len(self.trading.symbols) == 10, "Must be 10 coins"
        assert len(self.trading.timeframes) == 14, "Must be 14 timeframes"
        assert self.trading.mode_24_7 is True, "Must be crypto-only 24/7"
        return True

# Global config instance
config = ApexConfig()
