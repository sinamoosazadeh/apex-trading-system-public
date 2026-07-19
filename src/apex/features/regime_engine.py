"""Institutional Regime Intelligence Engine."""
from __future__ import annotations

import math
from typing import Sequence
from ..domain.market import MarketBar
from ..domain.regime import RegimeState
from .indicators import clamp, entropy_01, percentile_rank

class RegimeEngine:
    """Detects market regimes and transition probabilities."""

    def __init__(self, adx_len: int = 14, er_len: int = 20, rank_len: int = 200) -> None:
        self.adx_len = adx_len
        self.er_len = er_len
        self.rank_len = rank_len

    def _calculate_atr(self, bars: Sequence[MarketBar], period: int = 14) -> float:
        if len(bars) < period + 1: return 0.0
        trs = []
        for i in range(1, len(bars)):
            tr = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i-1].close),
                abs(bars[i].low - bars[i-1].close)
            )
            trs.append(tr)
        atr = sum(trs[:period]) / period
        for i in range(period, len(trs)):
            atr = (atr * (period - 1) + trs[i]) / period
        return atr

    def _calculate_adx(self, highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> float:
        if len(closes) < self.adx_len * 2: return 0.0
        plus_dm, minus_dm, tr_list = [], [], []
        for i in range(1, len(closes)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
            
        atr = sum(tr_list[:self.adx_len]) / self.adx_len
        dx_list = []
        for i in range(self.adx_len, len(tr_list)):
            atr = (atr * (self.adx_len - 1) + tr_list[i]) / self.adx_len
            p_dm = sum(plus_dm[i-self.adx_len+1:i+1]) / self.adx_len
            m_dm = sum(minus_dm[i-self.adx_len+1:i+1]) / self.adx_len
            p_di = (p_dm / atr * 100) if atr > 0 else 0
            m_di = (m_dm / atr * 100) if atr > 0 else 0
            dx = (abs(p_di - m_di) / (p_di + m_di) * 100) if (p_di + m_di) > 0 else 0
            dx_list.append(dx)
        return sum(dx_list[-self.adx_len:]) / self.adx_len if dx_list else 0.0

    def _calculate_efficiency_ratio(self, closes: Sequence[float]) -> float:
        if len(closes) < self.er_len: return 0.0
        change = abs(closes[-1] - closes[-self.er_len])
        volatility = sum(abs(closes[i] - closes[i-1]) for i in range(len(closes)-self.er_len, len(closes)))
        return change / volatility if volatility > 0 else 0.0

    def detect_regime(self, bars: Sequence[MarketBar]) -> RegimeState:
        if len(bars) < max(self.adx_len * 2, self.er_len, self.rank_len):
            return self._default_regime(bars[-1].timestamp if bars else 0)

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]
        
        adx = self._calculate_adx(highs, lows, closes)
        er = self._calculate_efficiency_ratio(closes)
        
        ema_fast = sum(closes[-10:]) / 10
        ema_slow = sum(closes[-50:]) / 50
        
        trend_score = (clamp(adx / 25.0, 0, 1) * 0.6) + (er * 0.4)
        trend_conf = clamp(trend_score, 0.0, 1.0)
        
        if ema_fast > ema_slow:
            if trend_conf > 0.7: trend_class = "STRONG_BULL"
            elif trend_conf > 0.5: trend_class = "BULL"
            elif trend_conf > 0.3: trend_class = "WEAK_BULL"
            else: trend_class = "NEUTRAL"
        elif ema_fast < ema_slow:
            if trend_conf > 0.7: trend_class = "STRONG_BEAR"
            elif trend_conf > 0.5: trend_class = "BEAR"
            elif trend_conf > 0.3: trend_class = "WEAK_BEAR"
            else: trend_class = "NEUTRAL"
        else:
            trend_class = "NEUTRAL"

        atr = self._calculate_atr(bars)
        atr_pct = percentile_rank([self._calculate_atr(bars[:i+1]) for i in range(len(bars))], atr)
        
        if atr_pct > 0.9: vol_class = "EXTREME"
        elif atr_pct > 0.7: vol_class = "HIGH"
        elif atr_pct > 0.3: vol_class = "NORMAL"
        elif atr_pct > 0.1: vol_class = "LOW"
        else: vol_class = "ULTRA_LOW"
        vol_conf = clamp(abs(atr_pct - 0.5) * 2.0, 0.0, 1.0)

        recent_vol = sum(volumes[-10:]) / 10
        avg_vol = sum(volumes[-50:]) / 50
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
        price_change = (closes[-1] - closes[-10]) / closes[-10] if closes[-10] > 0 else 0.0
        
        if price_change < -0.05 and vol_ratio > 1.5 and vol_class == "EXTREME":
            beh_class = "PANIC"
        elif price_change < -0.02 and vol_ratio > 1.2:
            beh_class = "FEAR"
        elif price_change > 0.05 and vol_ratio > 1.5 and vol_class == "EXTREME":
            beh_class = "EUPHORIA"
        elif price_change > 0.02 and vol_ratio > 1.2:
            beh_class = "GREED"
        elif abs(price_change) < 0.01 and vol_ratio < 0.8:
            beh_class = "ACCUMULATION" if closes[-1] > closes[-50] else "DISTRIBUTION"
        else:
            beh_class = "RECOVERY" if trend_class in ["BULL", "WEAK_BULL"] else "NEUTRAL"

        is_trending = trend_conf > 0.55
        is_ranging = trend_conf < 0.40
        is_transition = not is_trending and not is_ranging
        is_compression = vol_class in ["ULTRA_LOW", "LOW"] and is_ranging
        is_expansion = vol_class in ["HIGH", "EXTREME"] and is_trending
        
        regime_entropy = clamp(entropy_01(trend_conf) * 0.5 + entropy_01(vol_conf) * 0.5, 0.0, 1.0)
        trans_prob = {trend_class: 0.65}
        if is_trending:
            trans_prob["NEUTRAL"] = 0.25
            trans_prob["REVERSAL"] = 0.10
        else:
            trans_prob["TREND"] = 0.30
            trans_prob[trend_class] = 0.60

        return RegimeState(
            trend_class=trend_class,
            volatility_class=vol_class,
            liquidity_class="NORMAL",
            behavioral_class=beh_class,
            trend_confidence=trend_conf,
            volatility_confidence=vol_conf,
            regime_entropy=regime_entropy,
            expected_duration=42 if is_trending else 15,
            transition_prob=trans_prob,
            is_trending=is_trending,
            is_ranging=is_ranging,
            is_transition=is_transition,
            is_compression=is_compression,
            is_expansion=is_expansion,
            timestamp=bars[-1].timestamp
        )

    def _default_regime(self, timestamp: float) -> RegimeState:
        return RegimeState(
            trend_class="NEUTRAL", volatility_class="NORMAL", liquidity_class="NORMAL",
            behavioral_class="NEUTRAL", trend_confidence=0.0, volatility_confidence=0.0,
            regime_entropy=1.0, expected_duration=0, timestamp=timestamp
        )
