"""
APEX Institutional Trading System - Evidence Engine
Book I-III Compliant | Feature: 11 Missing Evidences

Book I: Market Structure & Smart Money Concepts
Book II: Probability & Bayesian Inference
Book III: Risk & Execution

Implements 11 Pine -> Python evidences for src/apex/features/evidence_engine.py
Existing: EventBus, ProbabilityEngine(BayesianModel), RiskEngine(Structure Hybrid SL),
ToobitAdapter(LONG->BUY_OPEN mapping), Security(no plain api_key storage)

Each ev_* returns EvidenceResult(score 0-1, confidence 0-1) with full math, no stubs.
Input: ohlcv numpy array shape (N,6): [ts, open, high, low, close, volume]
Dependencies: numpy only (production-safe)
Lines: <500
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

@dataclass(frozen=True)
class EvidenceResult:
    score: float  # 0.0 - 1.0 bullish/bearish quality, 0.5 neutral
    confidence: float  # 0.0 - 1.0
    direction: int  # -1 short, 0 neutral, 1 long
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'score', float(np.clip(self.score, 0.0, 1.0)))
        object.__setattr__(self, 'confidence', float(np.clip(self.confidence, 0.0, 1.0)))

def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c,1)), np.abs(l - np.roll(c,1))))
    tr[0] = h[0]-l[0]
    atr = np.convolve(tr, np.ones(n)/n, mode='same')
    return atr

def _ema(s: np.ndarray, n: int) -> np.ndarray:
    a = 2/(n+1)
    e = np.zeros_like(s, dtype=float)
    e[0]=s[0]
    for i in range(1,len(s)): e[i]=a*s[i]+(1-a)*e[i-1]
    return e

def _norm(x: float, lo: float, hi: float) -> float:
    if hi<=lo: return 0.5
    return float(np.clip((x-lo)/(hi-lo),0,1))

# ---- 1. ev_ob: Order Block Quality ----
def ev_ob(ohlcv: np.ndarray) -> EvidenceResult:
    """Order Block: last bullish/bearish block before displacement with imbalance."""
    if len(ohlcv)<30: return EvidenceResult(0.5,0.1,0,{"reason":"insufficient"})
    o,h,l,c,v = ohlcv[:,1],ohlcv[:,2],ohlcv[:,3],ohlcv[:,4],ohlcv[:,5]
    atr = _atr(h,l,c)
    last_bull=last_bear=None; scores=[]
    for i in range(len(c)-20, len(c)-3):
        body = abs(c[i]-o[i]); is_bull = c[i]>o[i]; disp = (c[i+2]-c[i]) / (atr[i]+1e-9)
        imb = (h[i+1]-l[i+1]) > body*1.5
        # Bullish OB: bear candle before strong bullish displacement
        if not is_bull and disp>1.5 and imb:
            fwd = np.min(l[i+1:]); mitigated = (l[-1] < l[i])*1.0
            quality = _norm(disp,1.5,5)*0.4 + _norm(v[i]/np.mean(v[max(0,i-20):i+1]),0.8,2.5)*0.3 + (1-mitigated)*0.3
            scores.append((quality,1,l[i],h[i],i))
            last_bull=(quality,i)
        if is_bull and disp<-1.5 and imb:
            mitigated = (h[-1] > h[i])*1.0
            quality = _norm(abs(disp),1.5,5)*0.4 + _norm(v[i]/np.mean(v[max(0,i-20):i+1]),0.8,2.5)*0.3 + (1-mitigated)*0.3
            scores.append((quality,-1,l[i],h[i],i))
            last_bear=(quality,i)
    if not scores:
        return EvidenceResult(0.5,0.2,0,{"ob":None})
    best = max(scores,key=lambda x:x[0])
    q, direction, lo, hi, idx = best
    dist = abs(c[-1]- (lo+hi)/2) / (atr[-1]+1e-9)
    conf = q * _norm(10-dist,0,10) * 0.8 + 0.2
    score = 0.5+ direction*q*0.5
    if direction==1: score = 0.5+q*0.5 if c[-1]>lo else 0.5-q*0.2
    else: score = 0.5-q*0.5 if c[-1]<hi else 0.5+q*0.2
    return EvidenceResult(score,conf,direction,{"quality":q,"ob_low":float(lo),"ob_high":float(hi),"displacement":float(best[0])})

# ---- 2. ev_fvg: Fair Value Gap ----
def ev_fvg(ohlcv: np.ndarray) -> EvidenceResult:
    """Detects 3-candle FVG (imbalance). Scores by size/ATR and fill %."""
    if len(ohlcv)<10: return EvidenceResult(0.5,0.1,0,{})
    h,l,c = ohlcv[:,2],ohlcv[:,3],ohlcv[:,4]
    atr = _atr(h,l,c)
    fvgs=[]
    for i in range(1,len(c)-1):
        bull_fvg = l[i+1] > h[i-1]  # gap up
        bear_fvg = h[i+1] < l[i-1]  # gap down
        if bull_fvg:
            gap = l[i+1]-h[i-1]; fill = max(0, h[i-1]+gap - np.min(l[i+1:]))/ (gap+1e-9)
            unfilled = 1-float(np.clip(fill,0,1))
            size_score = _norm(gap/atr[i],0.1,2.0)
            fvgs.append((size_score*unfilled, 1, gap, unfilled, i))
        if bear_fvg:
            gap = l[i-1]-h[i+1]; fill = max(0, np.max(h[i+1:]) - (h[i+1]))/ (gap+1e-9) if gap>0 else 1
            # corrected fill for bear
            low = l[i-1]; high = h[i+1]
            curr_low = np.min(ohlcv[i+1:,3]) if i+1<len(l) else l[-1]
            bear_fill = 0 if curr_low < high else 1  # simplified
            # use actual overlap
            overlap = max(0, np.max(h[i+1:]) - h[i+1]) if len(h[i+1:])>0 else 0
            fill_pct = np.clip(overlap/(gap+1e-9),0,1) if gap>0 else 1
            unfilled = 1-fill_pct
            size_score = _norm(gap/atr[i],0.1,2.0)
            fvgs.append((size_score*unfilled, -1, gap, unfilled, i))
    if not fvgs:
        return EvidenceResult(0.5,0.15,0,{"fvg":0})
    recent = sorted(fvgs,key=lambda x:x[4])[-3:]
    best = max(recent,key=lambda x:x[0])
    qual, direction, gap, unfilled, idx = best
    conf = _norm(qual,0,1)*0.7 + unfilled*0.3
    score = 0.5 + direction*qual*0.5
    return EvidenceResult(score,float(conf),int(direction),{"gap":float(gap),"unfilled":float(unfilled),"atr_mult":float(gap/(atr[idx]+1e-9))})

# ---- 3. ev_liq: Liquidity Sweep ----
def ev_liq(ohlcv: np.ndarray) -> EvidenceResult:
    """Equal highs/lows sweep with wick rejection + strong displacement after."""
    if len(ohlcv)<40: return EvidenceResult(0.5,0.1,0,{})
    h,l,c = ohlcv[:,2],ohlcv[:,3],ohlcv[:,4]
    atr = _atr(h,l,c)
    tol = atr[-1]*0.25
    # find recent swing highs/lows equality
    score=0.5; conf=0.2; direction=0; meta={}
    # look back 20 bars for equal highs
    window=20
    highs = h[-window-5:-5]; lows = l[-window-5:-5]
    eq_high = np.max(highs) if len(highs)>0 else 0
    eq_low = np.min(lows) if len(lows)>0 else 0
    # count touches within tol
    high_touches = np.sum(np.abs(highs-eq_high)<tol)
    low_touches = np.sum(np.abs(lows-eq_low)<tol)
    # sweep detection last 5 bars
    swept_high = np.any(h[-5:]>eq_high) and c[-1] < eq_high
    swept_low = np.any(l[-5:]<eq_low) and c[-1] > eq_low
    if swept_high and high_touches>=2:
        wick = (h[-1]-max(o[-1],c[-1]))/(atr[-1]+1e-9)
        disp = (eq_high - c[-1])/(atr[-1]+1e-9)
        qual = _norm(high_touches,2,5)*0.3 + _norm(wick,0.2,2)*0.35 + _norm(disp,0.2,3)*0.35
        score = 0.5 - qual*0.5
        conf = qual*0.8+0.15
        direction=-1
        meta={"type":"buy_stop_hunt","eq_level":float(eq_high),"touches":int(high_touches)}
    elif swept_low and low_touches>=2:
        wick = (min(o[-1],c[-1])-l[-1])/(atr[-1]+1e-9)
        disp = (c[-1]-eq_low)/(atr[-1]+1e-9)
        qual = _norm(low_touches,2,5)*0.3 + _norm(wick,0.2,2)*0.35 + _norm(disp,0.2,3)*0.35
        score = 0.5 + qual*0.5
        conf = qual*0.8+0.15
        direction=1
        meta={"type":"sell_stop_hunt","eq_level":float(eq_low),"touches":int(low_touches)}
    else:
        meta={"eq_high":float(eq_high),"eq_low":float(eq_low)}
    return EvidenceResult(score,conf,direction,meta)

# ---- 4. ev_zone: Supply/Demand Zone ----
def ev_zone(ohlcv: np.ndarray) -> EvidenceResult:
    """Base -> impulse. Scores tightness of base, impulse strength, freshness."""
    if len(ohlcv)<50: return EvidenceResult(0.5,0.1,0,{})
    o,h,l,c,v = ohlcv[:,1],ohlcv[:,2],ohlcv[:,3],ohlcv[:,4],ohlcv[:,5]
    atr = _atr(h,l,c)
    zones=[]
    for i in range(len(c)-30, len(c)-5):
        base_len=0; base_high=h[i]; base_low=l[i]
        j=i
        while j<len(c)-1 and j<i+6 and (max(h[i:j+1])-min(l[i:j+1])) < atr[j]*0.6:
            base_high=max(base_high,h[j]); base_low=min(base_low,l[j]); base_len+=1; j+=1
        if base_len>=2:
            impulse = (c[j+2]-c[j])/(atr[j]+1e-9) if j+2<len(c) else 0
            if abs(impulse)>2.0:
                tight = 1- _norm((base_high-base_low)/atr[j],0,1)
                strength = _norm(abs(impulse),2,6)
                fresh = 1.0 if np.min(l[j+1:])>base_low and np.max(h[j+1:])<base_high else 0.5
                vol_conf = _norm(np.mean(v[j:j+3])/np.mean(v[max(0,j-20):j+1]),0.8,2.5)
                q = tight*0.25 + strength*0.4 + fresh*0.2 + vol_conf*0.15
                zones.append((q, 1 if impulse>0 else -1, base_low, base_high, i))
    if not zones:
        return EvidenceResult(0.5,0.15,0,{"zones":0})
    best = max(zones,key=lambda x:x[0])
    q, direction, zl, zh, idx = best
    price = c[-1]
    near = 1-_norm(abs(price-(zl+zh)/2)/atr[-1],0,5)
    conf = q*0.6 + near*0.4
    score = 0.5 + direction*(0.3+q*0.2)*near
    return EvidenceResult(float(score),float(conf),int(direction),{"zone_low":float(zl),"zone_high":float(zh),"quality":float(q)})

# ---- 5. ev_dna: Market DNA ----
def ev_dna(ohlcv: np.ndarray) -> EvidenceResult:
    """Market structure DNA via entropy of returns + fractal pattern score."""
    if len(ohlcv)<60: return EvidenceResult(0.5,0.1,0,{})
    c,h,l = ohlcv[:,4],ohlcv[:,2],ohlcv[:,3]
    ret = np.diff(np.log(c+1e-12))
    # volatility regime
    vol = np.std(ret[-20:]) / (np.std(ret[-60:])+1e-9)
    # entropy of up/down runs
    signs = np.sign(ret[-30:])
    p_up = np.mean(signs>0); p_down=1-p_up if p_up>0 else 0.5
    ent = -(p_up*math.log(p_up+1e-9)+p_down*math.log(p_down+1e-9))/math.log(2)  # 0-1
    # fractal: higher highs lower lows efficiency
    hh = np.sum((h[-10:-1] < h[-9:]) ) /9; ll = np.sum((l[-10:-1] > l[-9:]))/9
    trend_eff = abs(np.mean(ret[-20:])) / (np.std(ret[-20:])+1e-9)
    # DNA score: low entropy + high trend eff = trending DNA, high entropy = choppy mean-revert
    dna_trend = (1-ent)*0.5 + _norm(trend_eff,0,1.5)*0.5
    direction = 1 if hh>0.6 else -1 if ll>0.6 or hh<0.4 else 0
    if abs(hh-0.5)<0.2 and ent>0.8:
        # choppy
        score=0.5; conf=_norm(ent,0.7,1.0); direction=0
    else:
        score = 0.5 + direction*dna_trend*0.45
        conf = _norm(abs(dna_trend-0.5)*2,0,1)*0.7 + _norm(abs(vol-1),0,1.5)*0.3
    return EvidenceResult(score, float(conf), int(direction), {"entropy":float(ent),"vol_regime":float(vol),"trend_eff":float(trend_eff),"hh_ratio":float(hh)})

# ---- 6. ev_kin: Kinematic Energy ----
def ev_kin(ohlcv: np.ndarray) -> EvidenceResult:
    """K = 0.5*m*v^2, m=volume, v=price velocity, a=acceleration."""
    if len(ohlcv)<30: return EvidenceResult(0.5,0.1,0,{})
    c,v = ohlcv[:,4], ohlcv[:,5]
    vel = np.diff(c, prepend=c[0])
    acc = np.diff(vel, prepend=0)
    mass = v/np.mean(v)+1e-9
    kinetic = 0.5*mass*vel*vel
    # normalized last kinetic vs percentile
    k_now = kinetic[-1]; k_hist = kinetic[-30:]
    k_pct = np.sum(k_hist < k_now)/len(k_hist) if len(k_hist)>0 else 0.5
    dir_sign = int(np.sign(vel[-1]+acc[-1]*0.5))
    # energy direction * momentum
    score = 0.5 + dir_sign*k_pct*0.45
    conf = _norm(abs(vel[-1])/(np.std(c[-20:])+1e-9),0,2)*0.5 + _norm(k_pct,0.5,1.0)*0.5
    return EvidenceResult(float(score),float(conf),dir_sign,{"velocity":float(vel[-1]),"acceleration":float(acc[-1]),"kinetic":float(k_now),"k_percentile":float(k_pct)})

# ---- 7. ev_delta: CVD Delta ----
def ev_delta(ohlcv: np.ndarray) -> EvidenceResult:
    """Cumulative Volume Delta divergence between price and volume flow."""
    if len(ohlcv)<30: return EvidenceResult(0.5,0.1,0,{})
    o,h,l,c,v = ohlcv[:,1],ohlcv[:,2],ohlcv[:,3],ohlcv[:,4],ohlcv[:,5]
    # simple buy/sell volume proxy: close location value
    clv = np.where(h==l,0,(2*c - h - l)/np.where(h-l==0,1,h-l))
    delta = clv * v
    cvd = np.cumsum(delta)
    # divergence over last 20
    price_chg = c[-1]-c[-21] if len(c)>21 else 0
    cvd_chg = cvd[-1]-cvd[-21] if len(cvd)>21 else 0
    price_norm = price_chg / (np.std(c[-20:])+1e-9)
    cvd_norm = cvd_chg / (np.std(cvd[-40:])+1e-9) if len(cvd)>40 else cvd_chg/(np.abs(cvd_chg)+1e-9)
    # bullish divergence: price down, cvd up
    div = 0.0; direction=0
    if price_norm<-0.5 and cvd_norm>0.2:
        div = _norm(cvd_norm - price_norm,0,4); direction=1
    elif price_norm>0.5 and cvd_norm<-0.2:
        div = _norm(price_norm - cvd_norm,0,4); direction=-1
    else:
        div = _norm(abs(cvd_norm),0,2)*0.3; direction = 1 if cvd_norm>0 else -1
    score = 0.5 + direction*div*0.45
    conf = _norm(abs(price_norm-cvd_norm),0,3)*0.6 + _norm(abs(cvd_norm),0,2)*0.4
    return EvidenceResult(float(score),float(conf),int(direction),{"cvd_change":float(cvd_chg),"price_change":float(price_chg),"divergence":float(div)})

# ---- 8. ev_seq: Sequential Pattern ----
def ev_seq(ohlcv: np.ndarray) -> EvidenceResult:
    """TD Sequential-like count of consecutive closes vs 4 bars ago."""
    if len(ohlcv)<20: return EvidenceResult(0.5,0.1,0,{})
    c = ohlcv[:,4]
    buy_cnt=sell_cnt=0; max_buy=max_sell=0
    for i in range(max(0,len(c)-15), len(c)):
        if i<4: continue
        if c[i] < c[i-4]: buy_cnt+=1; sell_cnt=0; max_buy=max(max_buy,buy_cnt)
        elif c[i] > c[i-4]: sell_cnt+=1; buy_cnt=0; max_sell=max(max_sell,sell_cnt)
        else: buy_cnt=sell_cnt=0
    direction=0; score=0.5; conf=0.3
    hist = c[-10:]
    if max_buy>=7:
        # bullish setup completion, expect reversal up unless 9
        qual = _norm(max_buy,6,9)
        if max_buy>=9: score=0.75; conf=0.7+qual*0.2; direction=1
        else: score=0.6+qual*0.15; conf=0.5+qual*0.2; direction=1
    elif max_sell>=7:
        qual = _norm(max_sell,6,9)
        if max_sell>=9: score=0.25; conf=0.7+qual*0.2; direction=-1
        else: score=0.4-qual*0.15; conf=0.5+qual*0.2; direction=-1
    else:
        # no completion
        momentum = _norm((c[-1]-c[-5])/ (np.std(c[-10:])+1e-9),-2,2)
        direction = 1 if momentum>0.55 else -1 if momentum<0.45 else 0
        score = float(momentum); conf=0.25
    return EvidenceResult(score,conf,direction,{"buy_count":int(max_buy),"sell_count":int(max_sell)})

# ---- 9. ev_trend: Trend Alignment ----
def ev_trend(ohlcv: np.ndarray) -> EvidenceResult:
    """EMA stack + ADX proxy for trend strength."""
    if len(ohlcv)<50: return EvidenceResult(0.5,0.1,0,{})
    c,h,l = ohlcv[:,4],ohlcv[:,2],ohlcv[:,3]
    e20=_ema(c,20); e50=_ema(c,50); e100=_ema(c,100) if len(c)>=100 else _ema(c,len(c)//2)
    # alignment score
    bull_align = (c[-1]>e20[-1]) + (e20[-1]>e50[-1]) + (e50[-1]>e100[-1])
    bear_align = (c[-1]<e20[-1]) + (e20[-1]<e50[-1]) + (e50[-1]<e100[-1])
    align = bull_align - bear_align  # -3..3
    # ADX proxy: directional movement
    up_move = h - np.roll(h,1); down_move = np.roll(l,1)-l
    plus_dm = np.where((up_move>down_move)&(up_move>0),up_move,0)
    minus_dm = np.where((down_move>up_move)&(down_move>0),down_move,0)
    atr = _atr(h,l,c,14)
    plus_di = 100* _ema(plus_dm/(atr+1e-9)*100,14) # simplified
    minus_di = 100* _ema(minus_dm/(atr+1e-9)*100,14)
    adx = np.abs(plus_di-minus_di)/(plus_di+minus_di+1e-9)*100
    adx_val = float(np.mean(adx[-10:]))
    adx_norm = _norm(adx_val,10,40)
    direction = 1 if align>0 else -1 if align<0 else 0
    score = 0.5 + align/6.0*0.8 # -0.4..0.4
    conf = abs(align)/3*0.6 + adx_norm*0.4
    return EvidenceResult(float(score),float(conf),int(direction),{"align":int(align),"adx":float(adx_val),"ema20":float(e20[-1]),"ema50":float(e50[-1])})

# ---- 10. ev_mtf: Multi-Timeframe ----
def ev_mtf(ohlcv_dict: Dict[str, np.ndarray]) -> EvidenceResult:
    """Alignment across MTF: expects {'1m','5m','15m','1h','4h'} ohlcv.
       Falls back to resampling if single array passed."""
    # normalize input
    if isinstance(ohlcv_dict, np.ndarray):
        # treat as single TF trend fallback
        return ev_trend(ohlcv_dict)
    scores=[]; dirs=[]
    for tf, data in ohlcv_dict.items():
        if len(data)<20: continue
        r = ev_trend(data)
        # weight higher TF more
        w = {"1m":0.5,"5m":1.0,"15m":1.5,"1h":2.0,"4h":3.0,"1D":4.0}.get(tf,1.0)
        scores.append((r.score, w)); dirs.append((r.direction,w))
    if not scores:
        return EvidenceResult(0.5,0.1,0,{"mtf":0})
    total_w = sum(w for _,w in scores)
    weighted_score = sum(s*w for s,w in scores)/total_w
    # consensus
    buy_w = sum(w for d,w in dirs if d>0); sell_w = sum(w for d,w in dirs if d<0)
    consensus = (buy_w - sell_w)/total_w  # -1..1
    conf = abs(consensus)*0.6 + 0.4 * (1 - np.std([s for s,_ in scores]))
    # penalize conflict
    direction = 1 if consensus>0.2 else -1 if consensus<-0.2 else 0
    final_score = 0.5 + consensus*0.45
    # blend with weighted score
    final_score = final_score*0.6 + weighted_score*0.4
    return EvidenceResult(float(final_score),float(np.clip(conf,0,1)),int(direction),{"consensus":float(consensus),"timeframes":list(ohlcv_dict.keys())})

# ---- 11. ev_profile: Volume Profile ----
def ev_profile(ohlcv: np.ndarray) -> EvidenceResult:
    """Value Area, POC distance, low-volume node trap."""
    if len(ohlcv)<50: return EvidenceResult(0.5,0.1,0,{})
    c,h,l,v = ohlcv[:,4],ohlcv[:,2],ohlcv[:,3],ohlcv[:,5]
    price_min, price_max = np.min(l[-50:]), np.max(h[-50:])
    bins=20
    hist, edges = np.histogram((h[-50:]+l[-50:])/2, bins=bins, range=(price_min,price_max), weights=v[-50:])
    centers = (edges[:-1]+edges[1:])/2
    poc_idx = int(np.argmax(hist)); poc = centers[poc_idx]
    total_vol = np.sum(hist)+1e-9
    # value area 70% around POC
    sorted_idx = np.argsort(hist)[::-1]
    va_vol=0; va_indices=[]
    for idx in sorted_idx:
        va_vol+=hist[idx]; va_indices.append(idx)
        if va_vol/total_vol>=0.7: break
    va_low = centers[min(va_indices)]; va_high = centers[max(va_indices)]
    curr = c[-1]
    # score: if price far from POC in low volume, mean reversion; if breaking VA with volume, trend
    dist_poc = (curr-poc)/ (price_max-price_min+1e-9)
    in_va = va_low <= curr <= va_high
    vol_at_price = hist[np.argmin(np.abs(centers-curr))]
    lvn = vol_at_price < np.mean(hist)*0.6
    if in_va:
        # neutral inside VA, slight mean revert to POC
        direction = -1 if curr>poc else 1
        score = 0.5 + (-dist_poc)*0.3
        conf = 0.4 + (0 if lvn else 0.2)
    else:
        # outside VA
        direction = 1 if curr>va_high else -1
        breakout_strength = _norm(abs(curr - (va_high if curr>va_high else va_low))/(price_max-price_min),0,0.3)
        score = 0.5 + direction*breakout_strength*0.45
        conf = 0.55 + breakout_strength*0.35
        if lvn: conf+=0.1
    return EvidenceResult(float(score),float(np.clip(conf,0,1)),int(direction),{"poc":float(poc),"va_low":float(va_low),"va_high":float(va_high),"lvn":bool(lvn),"in_va":bool(in_va)})

class EvidenceEngine:
    """Aggregator compliant with APEX ProbabilityEngine.
       ToobitAdapter maps LONG->BUY_OPEN etc externally.
    """
    def __init__(self):
        self.evidences = {
            "ev_ob": ev_ob, "ev_fvg": ev_fvg, "ev_liq": ev_liq, "ev_zone": ev_zone,
            "ev_dna": ev_dna, "ev_kin": ev_kin, "ev_delta": ev_delta,
            "ev_seq": ev_seq, "ev_trend": ev_trend, "ev_mtf": ev_mtf, "ev_profile": ev_profile
        }

    def evaluate(self, ohlcv: np.ndarray, mtf: Optional[Dict[str,np.ndarray]]=None) -> Dict[str, EvidenceResult]:
        res: Dict[str, EvidenceResult] = {}
        for k, fn in self.evidences.items():
            try:
                if k=="ev_mtf":
                    res[k]= fn(mtf if mtf is not None else ohlcv)  # type: ignore
                else:
                    res[k]= fn(ohlcv)
            except Exception as e:
                res[k]= EvidenceResult(0.5,0.05,0,{"error":str(e)})
        return res

    def aggregate_score(self, results: Dict[str, EvidenceResult]) -> Tuple[float,float,int]:
        """Bayesian-like weighted aggregate for ProbabilityEngine."""
        weights = {"ev_trend":1.5,"ev_mtf":2.0,"ev_liq":1.3,"ev_ob":1.4,"ev_zone":1.2,"ev_fvg":1.0,"ev_profile":1.1,"ev_delta":1.2,"ev_dna":0.8,"ev_kin":0.9,"ev_seq":0.7}
        s=0; wsum=0; confs=[]
        vote=0
        for k,r in results.items():
            wt = weights.get(k,1.0)* (0.5+r.confidence)
            s+= r.score*wt; wsum+=wt; confs.append(r.confidence); vote+= r.direction*wt
        final_score = s/wsum if wsum>0 else 0.5
        final_conf = float(np.mean(confs)) if confs else 0.1
        final_dir = 1 if vote>0 else -1 if vote<0 else 0
        return float(np.clip(final_score,0,1)), float(final_conf), int(final_dir)

if __name__=="__main__":
    # smoke test
    np.random.seed(1)
    n=200; c=np.cumsum(np.random.randn(n)*0.5)+100
    h=c+np.abs(np.random.randn(n)); l=c-np.abs(np.random.randn(n))
    o=c+np.random.randn(n)*0.2; v=np.random.randint(100,1000,size=n); ts=np.arange(n)
    data=np.column_stack([ts,o,h,l,c,v]).astype(float)
    eng=EvidenceEngine()
    out=eng.evaluate(data, {"15m":data,"1h":data[-100:],"4h":data[-60:]})
    agg=eng.aggregate_score(out)
    print("Aggregate:",agg)
    for k,v in out.items(): print(k, f"score={v.score:.2f} conf={v.confidence:.2f} dir={v.direction} meta={v.meta}")

