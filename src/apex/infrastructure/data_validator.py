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
