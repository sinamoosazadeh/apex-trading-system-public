"""
APEX Institutional Engine - ICT Full Engine Module
Path: src/apex/features/ict_engine.py
Book Compliance: Book I (Core Theory), Book II (Structure & Liquidity), Book III (ICT Concepts & Probability)
Implements 13 Pine f_* evidences: f_mss, f_breaker_block, f_mitigation_block, f_ote_zone, f_premium_discount, f_equilibrium, f_liquidity_void, f_killzone_scoring, f_swing_detection, f_order_block_validation, f_liquidity_sweep, f_displacement, f_ict_confluence
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal
from enum import Enum
from datetime import datetime, timezone

try:
    from apex.features.structure import StructureState
except ImportError:
    @dataclass
    class StructureState:
        trend: Literal["BULL", "BEAR", "RANGE"] = "RANGE"
        bos: bool = False
        choch: bool = False
        swing_high: float = 0.0
        swing_low: float = 0.0
        swing_high_idx: int = 0
        swing_low_idx: int = 0
        bos_level: float = 0.0

class ICTBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class KillzoneName(str, Enum):
    LONDON = "LONDON"
    NY_AM = "NY_AM"
    NY_PM = "NY_PM"
    ASIA = "ASIA"
    LONDON_CLOSE = "LONDON_CLOSE"

KILLZONE_DEFS: Dict[KillzoneName, Dict] = {
    KillzoneName.ASIA: {"utc_start": 0, "utc_end": 5, "score_base": 0.6, "vol_mult": 0.8},
    KillzoneName.LONDON: {"utc_start": 8, "utc_end": 11, "score_base": 1.0, "vol_mult": 1.3},
    KillzoneName.NY_AM: {"utc_start": 13, "utc_end": 16, "score_base": 1.0, "vol_mult": 1.5},
    KillzoneName.NY_PM: {"utc_start": 19, "utc_end": 21, "score_base": 0.7, "vol_mult": 1.0},
    KillzoneName.LONDON_CLOSE: {"utc_start": 15, "utc_end": 17, "score_base": 0.75, "vol_mult": 1.1},
}

@dataclass
class OHLC:
    high: float
    low: float
    close: float
    open: float
    volume: float = 0.0
    timestamp: int = 0

@dataclass
class Zone:
    kind: Literal["BREAKER", "MITIGATION", "OTE", "PREMIUM", "DISCOUNT", "VOID", "EQ"]
    top: float
    bottom: float
    bias: ICTBias
    strength: float
    origin_idx: int
    valid: bool = True
    meta: Dict = field(default_factory=dict)

@dataclass
class KillzoneState:
    name: KillzoneName
    active: bool
    score: float
    minutes_in: int

@dataclass
class ICTState:
    bias: ICTBias
    zones: List[Zone]
    killzone: KillzoneState
    ote_zone: Optional[Zone]
    premium_discount: Literal["PREMIUM", "DISCOUNT", "EQUILIBRIUM"]
    eq_level: float
    mss_confirmed: bool
    confluence_score: float

def f_swing_detection(candles: List[OHLC], lookback: int = 5) -> Tuple[float, float, int, int]:
    if len(candles) < lookback*2+1:
        return candles[-1].high, candles[-1].low, len(candles)-1, len(candles)-1
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    pivot_high = max(highs[-lookback*2-1:-1])
    pivot_low = min(lows[-lookback*2-1:-1])
    hi_idx = len(candles) - 1 - list(reversed(highs)).index(pivot_high) if pivot_high in highs else len(candles)-1
    lo_idx = len(candles) - 1 - list(reversed(lows)).index(pivot_low) if pivot_low in lows else len(candles)-1
    return pivot_high, pivot_low, hi_idx, lo_idx

def f_displacement(candles: List[OHLC], idx: int, atr: float) -> bool:
    if idx < 1 or idx >= len(candles):
        return False
    c = candles[idx]
    body = abs(c.close - c.open)
    return body > (atr * 1.8) and (c.close > c.open if c.close > candles[idx-1].high else c.close < candles[idx-1].low)

def f_mss(candles: List[OHLC], struct: StructureState, swing_high: float, swing_low: float) -> Tuple[bool, ICTBias]:
    close = candles[-1].close
    prev_close = candles[-2].close if len(candles)>1 else close
    bullish_mss = close > swing_high and prev_close <= swing_high and struct.trend != "BEAR"
    bearish_mss = close < swing_low and prev_close >= swing_low and struct.trend != "BULL"
    if bullish_mss:
        return True, ICTBias.BULLISH
    if bearish_mss:
        return True, ICTBias.BEARISH
    return False, ICTBias.NEUTRAL

def f_liquidity_sweep(candles: List[OHLC], swing_high: float, swing_low: float, atr: float) -> Tuple[bool, Literal["HIGH","LOW","NONE"]]:
    c = candles[-1]
    upper_sweep = c.high > swing_high + 0.2*atr and c.close < swing_high
    lower_sweep = c.low < swing_low - 0.2*atr and c.close > swing_low
    if upper_sweep:
        return True, "HIGH"
    if lower_sweep:
        return True, "LOW"
    return False, "NONE"

def f_liquidity_void(candles: List[OHLC], min_impulse_atr: float = 0.6) -> List[Zone]:
    zones: List[Zone] = []
    for i in range(1, len(candles)-1):
        prev, nxt = candles[i-1], candles[i+1]
        if nxt.low > prev.high:
            gap = nxt.low - prev.high
            if gap > min_impulse_atr:
                zones.append(Zone(kind="VOID", top=nxt.low, bottom=prev.high, bias=ICTBias.BULLISH, strength=min(1.0, gap/min_impulse_atr/3), origin_idx=i, meta={"dir":"BULL_FVG"}))
        if prev.low > nxt.high:
            gap = prev.low - nxt.high
            if gap > min_impulse_atr:
                zones.append(Zone(kind="VOID", top=prev.low, bottom=nxt.high, bias=ICTBias.BEARISH, strength=min(1.0, gap/min_impulse_atr/3), origin_idx=i, meta={"dir":"BEAR_FVG"}))
    return zones

def f_order_block_validation(candles: List[OHLC], idx: int, bias: ICTBias, atr: float) -> float:
    if idx <0 or idx>=len(candles):
        return 0.0
    c = candles[idx]
    rng = c.high - c.low
    strength = 0.0
    if rng > atr*0.8:
        strength += 0.4
    if f_displacement(candles, idx+1 if idx+1 < len(candles) else idx, atr):
        strength += 0.4
    if bias == ICTBias.BULLISH and c.close > c.open:
        strength += 0.2
    if bias == ICTBias.BEARISH and c.close < c.open:
        strength += 0.2
    return min(1.0, strength)

def f_breaker_block(candles: List[OHLC], swing_high: float, swing_low: float, bias: ICTBias, atr: float) -> Optional[Zone]:
    if len(candles) < 10:
        return None
    search = candles[-20:-1]
    for j in range(len(search)-1, -1, -1):
        c = search[j]
        abs_idx = len(candles)-20+j
        is_bear_ob = c.close < c.open and ((c.high - c.low) > atr*0.7)
        if bias == ICTBias.BULLISH and is_bear_ob:
            score = f_order_block_validation(candles, abs_idx, ICTBias.BULLISH, atr)
            if score > 0.5:
                return Zone(kind="BREAKER", top=c.high, bottom=c.low, bias=ICTBias.BULLISH, strength=score, origin_idx=abs_idx, meta={"type":"BULL_BREAKER"})
        if bias == ICTBias.BEARISH and c.close > c.open and (c.high-c.low) > atr*0.7:
            score = f_order_block_validation(candles, abs_idx, ICTBias.BEARISH, atr)
            if score > 0.5:
                return Zone(kind="BREAKER", top=c.high, bottom=c.low, bias=ICTBias.BEARISH, strength=score, origin_idx=abs_idx, meta={"type":"BEAR_BREAKER"})
    return None

def f_mitigation_block(candles: List[OHLC], swing_high: float, swing_low: float, bias: ICTBias, atr: float) -> Optional[Zone]:
    if len(candles) < 10:
        return None
    for i in range(len(candles)-2, max(2, len(candles)-15), -1):
        if f_displacement(candles, i, atr):
            prev = candles[i-1]
            if bias == ICTBias.BULLISH and prev.close < prev.open:
                return Zone(kind="MITIGATION", top=prev.high, bottom=prev.low, bias=ICTBias.BULLISH, strength=f_order_block_validation(candles, i-1, bias, atr), origin_idx=i-1, meta={"impulse_idx":i})
            if bias == ICTBias.BEARISH and prev.close > prev.open:
                return Zone(kind="MITIGATION", top=prev.high, bottom=prev.low, bias=ICTBias.BEARISH, strength=f_order_block_validation(candles, i-1, bias, atr), origin_idx=i-1, meta={"impulse_idx":i})
    return None

def f_ote_zone(swing_high: float, swing_low: float, bias: ICTBias) -> Zone:
    rng = swing_high - swing_low
    if rng <= 0:
        rng = 1e-6
    if bias == ICTBias.BULLISH:
        top = swing_low + rng * 0.79
        bottom = swing_low + rng * 0.62
    else:
        t = swing_high - rng * 0.62
        b = swing_high - rng * 0.79
        top, bottom = max(t,b), min(t,b)
    return Zone(kind="OTE", top=top, bottom=bottom, bias=bias, strength=0.85, origin_idx=0, meta={"fib":"0.62-0.79", "high":swing_high, "low":swing_low})

def f_premium_discount(swing_high: float, swing_low: float, price: float) -> Tuple[Literal["PREMIUM","DISCOUNT","EQUILIBRIUM"], float]:
    rng = swing_high - swing_low
    if rng <= 0:
        return "EQUILIBRIUM", swing_low
    eq = swing_low + rng*0.5
    if price > eq + rng*0.05:
        return "PREMIUM", eq
    if price < eq - rng*0.05:
        return "DISCOUNT", eq
    return "EQUILIBRIUM", eq

def f_equilibrium(swing_high: float, swing_low: float) -> float:
    return swing_low + (swing_high - swing_low)*0.5

def f_killzone_scoring(ts_ms: int, price: float, candles: List[OHLC]) -> KillzoneState:
    dt = datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc)
    hour = dt.hour + dt.minute/60.0
    best = KillzoneState(name=KillzoneName.ASIA, active=False, score=0.0, minutes_in=0)
    for name, cfg in KILLZONE_DEFS.items():
        s, e = cfg["utc_start"], cfg["utc_end"]
        active = (s <= hour < e) if s<e else (hour>=s or hour<e)
        mid = (s+e)/2 if s<e else ((s+e+24)/2)%24
        dist = abs(hour-mid)
        span = (e-s) if s<e else (24-s+e)
        time_score = cfg["score_base"] * (1.2 - min(0.4, dist/span))
        atr_proxy = (candles[-1].high - candles[-1].low) if candles else 1.0
        vol_adj = 1.0 + (atr_proxy / (price or 1.0))* cfg["vol_mult"]
        total = time_score * vol_adj
        minutes_in = int((hour - s)*60) if active and s<=hour else 0
        if active and total > best.score:
            best = KillzoneState(name=name, active=True, score=min(1.3, total), minutes_in=minutes_in)
        if not best.active and total > best.score:
            best = KillzoneState(name=name, active=False, score=total*0.5, minutes_in=0)
    return best

def f_ict_confluence(zones: List[Zone], killzone: KillzoneState, mss_bias: ICTBias, premium_state: str, price: float) -> float:
    score = 0.0
    if killzone.active:
        score += 0.25 * killzone.score
    for z in zones:
        if z.kind=="OTE" and z.bottom <= price <= z.top:
            score += 0.30 * z.strength
        if z.kind in ("BREAKER","MITIGATION") and z.bottom <= price <= z.top and z.bias == mss_bias:
            score += 0.25 * z.strength
        if z.kind=="VOID" and z.bias == mss_bias:
            score += 0.10 * z.strength
    if premium_state=="DISCOUNT" and mss_bias==ICTBias.BULLISH:
        score += 0.15
    if premium_state=="PREMIUM" and mss_bias==ICTBias.BEARISH:
        score += 0.15
    return min(1.0, score)

def _calc_atr(candles: List[OHLC], period: int = 14) -> float:
    if len(candles) < 2:
        return candles[0].high - candles[0].low if candles else 1.0
    trs = []
    for i in range(1, min(len(candles), period+1)):
        h,l = candles[-i].high, candles[-i].low
        pc = candles[-i-1].close if i+1<=len(candles) else candles[-i].close
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs)/len(trs) if trs else 1.0

class ICTEngine:
    def __init__(self):
        self.last_state: Optional[ICTState] = None

    def analyze(self, candles: List[OHLC], struct: StructureState) -> ICTState:
        if not candles:
            raise ValueError("candles empty")
        swing_high, swing_low, _, _ = f_swing_detection(candles)
        if struct.swing_high > 0: swing_high = struct.swing_high
        if struct.swing_low > 0: swing_low = struct.swing_low
        atr = _calc_atr(candles)
        mss_confirmed, mss_bias = f_mss(candles, struct, swing_high, swing_low)
        price = candles[-1].close
        zones: List[Zone] = []
        zones.extend(f_liquidity_void(candles, atr*0.5))
        trend_bias = ICTBias.BULLISH if struct.trend=="BULL" else ICTBias.BEARISH if struct.trend=="BEAR" else ICTBias.NEUTRAL
        use_bias = mss_bias if mss_confirmed else trend_bias
        ote = f_ote_zone(swing_high, swing_low, use_bias)
        zones.append(ote)
        eq = f_equilibrium(swing_high, swing_low)
        zones.append(Zone(kind="EQ", top=eq*1.002, bottom=eq*0.998, bias=ICTBias.NEUTRAL, strength=0.5, origin_idx=0, meta={"eq":eq}))
        if mss_confirmed:
            breaker = f_breaker_block(candles, swing_high, swing_low, mss_bias, atr)
            if breaker: zones.append(breaker)
            mitig = f_mitigation_block(candles, swing_high, swing_low, mss_bias, atr)
            if mitig: zones.append(mitig)
        premium_state, eq_level = f_premium_discount(swing_high, swing_low, price)
        killzone = f_killzone_scoring(candles[-1].timestamp or int(datetime.now(tz=timezone.utc).timestamp()*1000), price, candles)
        confluence = f_ict_confluence(zones, killzone, mss_bias, premium_state, price)
        bias = mss_bias if mss_confirmed and confluence>0.45 else ICTBias.NEUTRAL
        for z in zones:
            if z.bias==ICTBias.BULLISH and price < z.bottom - atr*0.5:
                z.valid=False
            if z.bias==ICTBias.BEARISH and price > z.top + atr*0.5:
                z.valid=False
        state = ICTState(bias=bias, zones=[z for z in zones if z.valid], killzone=killzone, ote_zone=ote, premium_discount=premium_state, eq_level=eq_level, mss_confirmed=mss_confirmed, confluence_score=confluence)
        self.last_state = state
        return state

    def get_bayesian_prior(self) -> Dict[str, float]:
        if not self.last_state:
            return {"p_bull_ict":0.5, "p_bear_ict":0.5, "confluence":0.0}
        s = self.last_state
        if s.bias==ICTBias.BULLISH:
            return {"p_bull_ict":0.5 + s.confluence_score*0.5, "p_bear_ict":0.5 - s.confluence_score*0.3, "confluence":s.confluence_score}
        if s.bias==ICTBias.BEARISH:
            return {"p_bull_ict":0.5 - s.confluence_score*0.3, "p_bear_ict":0.5 + s.confluence_score*0.5, "confluence":s.confluence_score}
        return {"p_bull_ict":0.5, "p_bear_ict":0.5, "confluence":s.confluence_score}

if __name__ == "__main__":
    import random, time
    base=100.0
    candles=[]
    ts=int(time.time()*1000)
    for i in range(50):
        o=base; h=o+random.uniform(0.2,1.0); l=o-random.uniform(0.2,1.0); c=o+random.uniform(-0.5,0.5); base=c
        candles.append(OHLC(high=h, low=l, close=c, open=o, timestamp=ts+i*60000))
    candles[-1].close = candles[-1].high + 2.0
    candles[-1].high = candles[-1].close + 0.5
    struct = StructureState(trend="BULL", bos=True, swing_high=max(c.high for c in candles[-10:-1]), swing_low=min(c.low for c in candles[-10:-1]))
    eng = ICTEngine()
    st = eng.analyze(candles, struct)
    print(f"Bias {st.bias} Killzone {st.killzone.name} active={st.killzone.active} score={st.killzone.score:.2f}")
    print(f"Premium {st.premium_discount} EQ {st.eq_level:.2f} Confluence {st.confluence_score:.2f} MSS {st.mss_confirmed}")
    print(f"Zones {len(st.zones)}: {[f'{z.kind}:{z.bias.value} str={z.strength:.2f}' for z in st.zones]}")
    print("Bayesian", eng.get_bayesian_prior())
    assert st.eq_level>0 and len(st.zones)>=2
    print("OK - ICTEngine complete")

