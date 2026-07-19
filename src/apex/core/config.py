"""
src/apex/core/config.py - APEX Institutional Config System
Book Compliance: I-III Blueprints
- Book I Ch.3: Central config for 56-file codebase, EventBus topics, ToobitAdapter LONG->BUY_OPEN
- Book II 2.6: Strict Pydantic validation, no silent risk defaults, RR>=1.5, Hybrid weights sum 1.0,
               13 evidences sum~1.0, SL range, probability ordering
- Book III: Security - API keys via SecretStr (never plain str), env override, masked repr/fingerprint
- Pine: 13 evidences fully encoded in signal.yaml for BayesianModel
- Production: Full typing, <500 lines, no TODO/pass/NotImplemented, runnable
"""
from __future__ import annotations
import os, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path as FP
from typing import Dict, List, Optional, Any, Literal, Tuple
import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator, ValidationError

CONFIG_TEMPLATES: Dict[str, str] = {
"market.yaml": """exchange:
  name: "toobit"
  adapter: "ToobitAdapter"
  mapping: {LONG: "BUY_OPEN", SHORT: "SELL_OPEN", CLOSE_LONG: "SELL_CLOSE", CLOSE_SHORT: "BUY_CLOSE"}
  credentials: {api_key: "${TOOBIT_API_KEY}", api_secret: "${TOOBIT_API_SECRET}", testnet: true}
symbols: ["BTCUSDT","ETHUSDT","SOLUSDT"]
timeframe: "15m"
allowed_timeframes: ["1m","5m","15m","1h","4h"]
datafeed: {type: "ccxt", ohlcv_limit: 500, ws_enabled: true, reconnect_attempts: 5}
event_bus: {topics: ["market.tick","signal.generated","risk.approved","execution.fill"], max_queue_size: 10000, persistent: true}
""",
"signal.yaml": """probability_engine: {model: "BayesianModel", prior_alpha: 2.0, prior_beta: 2.0, decay_factor: 0.95, min_samples: 50}
thresholds: {min_probability: 0.62, high_confidence: 0.75, execution_threshold: 0.68}
evidences:
  e01_structure_break: {weight: 0.15, enabled: true, lookback: 20}
  e02_order_block: {weight: 0.12, enabled: true, lookback: 50}
  e03_fvg_imbalance: {weight: 0.10, enabled: true, lookback: 30}
  e04_liquidity_sweep: {weight: 0.10, enabled: true, lookback: 20}
  e05_momentum_divergence: {weight: 0.08, enabled: true, lookback: 14}
  e06_volume_profile: {weight: 0.07, enabled: true, lookback: 100}
  e07_volatility_regime: {weight: 0.07, enabled: true, lookback: 50}
  e08_trend_structure: {weight: 0.08, enabled: true, lookback: 100}
  e09_sr_flip: {weight: 0.05, enabled: true, lookback: 40}
  e10_ema_alignment: {weight: 0.05, enabled: true, lookback: 21}
  e11_rsi_filter: {weight: 0.04, enabled: true, lookback: 14}
  e12_session_liquidity: {weight: 0.05, enabled: true, lookback: 24}
  e13_htf_confluence: {weight: 0.04, enabled: true, lookback: 100}
aggregation: {method: "bayesian_weighted", normalize_weights: true, require_min_evidences: 3}
""",
"risk.yaml": """risk_engine: {model: "StructureHybridSL", max_risk_per_trade_pct: 1.0, max_daily_loss_pct: 3.0, max_open_positions: 3, max_correlation_exposure: 0.7, account_size_usdt: 10000.0, leverage_max: 10, use_cross_margin: false}
stop_loss: {type: "structure_hybrid", structure_lookback: 20, atr_multiplier: 1.5, atr_period: 14, hybrid_weight_structure: 0.6, hybrid_weight_atr: 0.4, min_sl_pct: 0.3, max_sl_pct: 3.0, breakeven_trigger_rr: 1.0, breakeven_offset_pct: 0.1}
take_profit: {rr_ratio: 2.5, partials: [{rr: 1.0, pct_close: 0.3},{rr: 2.0, pct_close: 0.3},{rr: 2.5, pct_close: 0.4}], trail_enabled: true, trail_atr_multiplier: 1.0}
validation: {enforce_rr_min: 1.5, enforce_stop_presence: true, require_risk_approval: true}
"""
}
TF = Literal["1m","5m","15m","1h","4h","1d"]

class CredSchema(BaseModel):
    api_key: SecretStr = Field(...)
    api_secret: SecretStr = Field(...)
    testnet: bool = True
    @field_validator("api_key","api_secret", mode="before")
    @classmethod
    def env(cls, v: Any)->Any:
        if isinstance(v,str) and v.startswith("${") and v.endswith("}"):
            return SecretStr(os.getenv(v[2:-1],""))
        return v if isinstance(v, SecretStr) else SecretStr(v)
    def masked(self)->str:
        s=self.api_key.get_secret_value(); return "***" if len(s)<=8 else f"{s[:4]}***{s[-4:]}"
    def fingerprint(self)->str:
        s=self.api_key.get_secret_value()+self.api_secret.get_secret_value()
        return "no-key" if not s.strip() else hashlib.sha256(s.encode()).hexdigest()[:12]

class ExchSchema(BaseModel):
    name: str = Field(..., pattern=r"^[a-z0-9_]+$")
    adapter: Literal["ToobitAdapter","BinanceAdapter","BybitAdapter"]="ToobitAdapter"
    mapping: Dict[str,str]=Field(default_factory=lambda:{"LONG":"BUY_OPEN","SHORT":"SELL_OPEN"})
    credentials: CredSchema
    @field_validator("mapping")
    @classmethod
    def chk_map(cls,v:Dict[str,str])->Dict[str,str]:
        if v.get("LONG") and v["LONG"]!="BUY_OPEN": raise ValueError("Toobit LONG must be BUY_OPEN")
        if not {"LONG","SHORT"}.issubset(v): raise ValueError("mapping missing LONG/SHORT")
        return v

class DatafeedSchema(BaseModel):
    type: Literal["ccxt","websocket","toobit_ws"]="ccxt"
    ohlcv_limit: int=Field(500,ge=100,le=1500); ws_enabled: bool=True; reconnect_attempts: int=Field(5,ge=1,le=20)
class EventBusSchema(BaseModel):
    topics: List[str]=Field(...,min_length=1); max_queue_size: int=Field(10000,ge=100,le=100000); persistent: bool=True

class MarketSchema(BaseModel):
    exchange: ExchSchema; symbols: List[str]=Field(...,min_length=1)
    timeframe: TF="15m"; allowed_timeframes: List[TF]=Field(default_factory=lambda:["1m","5m","15m","1h","4h"])
    datafeed: DatafeedSchema=Field(default_factory=DatafeedSchema); event_bus: EventBusSchema
    @field_validator("symbols")
    @classmethod
    def chk_sym(cls,v:List[str])->List[str]:
        for s in v:
            if not s.endswith("USDT") or len(s)<6: raise ValueError(f"Bad symbol {s}")
        if len(set(v))!=len(v): raise ValueError("Duplicate symbols")
        return v
    @field_validator("timeframe")
    @classmethod
    def chk_tf(cls,v:str,info)->str:
        allowed=info.data.get("allowed_timeframes",[])
        if allowed and v not in allowed: raise ValueError(f"tf {v} not in {allowed}")
        return v

class EvSchema(BaseModel):
    weight: float=Field(...,ge=0.01,le=0.5); enabled: bool=True; lookback: int=Field(...,ge=5,le=500)
class ProbSchema(BaseModel):
    model: Literal["BayesianModel","LogisticRegression"]="BayesianModel"
    prior_alpha: float=Field(2.0,ge=0.1,le=10.0); prior_beta: float=Field(2.0,ge=0.1,le=10.0)
    decay_factor: float=Field(0.95,ge=0.8,le=0.999); min_samples: int=Field(50,ge=10,le=1000)
class ThreshSchema(BaseModel):
    min_probability: float=Field(0.62,ge=0.5,le=0.9); high_confidence: float=Field(0.75,ge=0.6,le=0.95)
    execution_threshold: float=Field(0.68,ge=0.5,le=0.95)
    @model_validator(mode="after")
    def order(self)->"ThreshSchema":
        if not (self.min_probability<=self.execution_threshold<=self.high_confidence): raise ValueError("Require min<=exec<=high")
        if self.high_confidence-self.min_probability<0.05: raise ValueError("Spread too narrow")
        return self
class SignalSchema(BaseModel):
    probability_engine: ProbSchema; thresholds: ThreshSchema; evidences: Dict[str,EvSchema]; aggregation: Dict[str,Any]
    @field_validator("evidences")
    @classmethod
    def chk_13(cls,v:Dict[str,EvSchema])->Dict[str,EvSchema]:
        if len(v)!=13: raise ValueError(f"Need 13 evidences got {len(v)}")
        tot=sum(e.weight for e in v.values() if e.enabled)
        if not 0.9<=tot<=1.1: raise ValueError(f"Weights sum ~1.0 got {tot}")
        return v

class RiskEngSchema(BaseModel):
    model: Literal["StructureHybridSL","FixedSL","ATRSL"]="StructureHybridSL"
    max_risk_per_trade_pct: float=Field(1.0,ge=0.1,le=5.0); max_daily_loss_pct: float=Field(3.0,ge=0.5,le=10.0)
    max_open_positions: int=Field(3,ge=1,le=10); max_correlation_exposure: float=Field(0.7,ge=0.1,le=1.0)
    account_size_usdt: float=Field(...,gt=0); leverage_max: int=Field(10,ge=1,le=50); use_cross_margin: bool=False
    @model_validator(mode="after")
    def hier(self)->"RiskEngSchema":
        if self.max_daily_loss_pct<self.max_risk_per_trade_pct: raise ValueError("daily < per_trade")
        return self
class SLSchema(BaseModel):
    type: Literal["structure_hybrid","structure","atr","fixed"]="structure_hybrid"
    structure_lookback: int=Field(20,ge=5,le=200); atr_multiplier: float=Field(1.5,ge=0.5,le=5.0)
    atr_period: int=Field(14,ge=5,le=50); hybrid_weight_structure: float=Field(0.6,ge=0.0,le=1.0)
    hybrid_weight_atr: float=Field(0.4,ge=0.0,le=1.0); min_sl_pct: float=Field(0.3,ge=0.05,le=2.0)
    max_sl_pct: float=Field(3.0,ge=0.5,le=10.0); breakeven_trigger_rr: float=Field(1.0,ge=0.5,le=3.0)
    breakeven_offset_pct: float=Field(0.1,ge=0.0,le=0.5)
    @model_validator(mode="after")
    def hyb(self)->"SLSchema":
        if abs(self.hybrid_weight_structure+self.hybrid_weight_atr-1.0)>1e-6: raise ValueError("weights sum!=1")
        if self.min_sl_pct>=self.max_sl_pct: raise ValueError("min>=max sl")
        if self.type=="structure_hybrid" and self.hybrid_weight_structure<0.3: raise ValueError("hybrid structural weight <0.3")
        return self
class PartSchema(BaseModel):
    rr: float=Field(...,ge=0.5,le=10.0); pct_close: float=Field(...,ge=0.05,le=1.0)
class TPSchema(BaseModel):
    rr_ratio: float=Field(2.5,ge=1.0,le=10.0); partials: List[PartSchema]; trail_enabled: bool=True
    trail_atr_multiplier: float=Field(1.0,ge=0.5,le=3.0)
    @field_validator("partials")
    @classmethod
    def chk_part(cls,v:List[PartSchema])->List[PartSchema]:
        if abs(sum(p.pct_close for p in v)-1.0)>1e-6: raise ValueError("partials must sum 1.0")
        if [p.rr for p in v]!=sorted(p.rr for p in v): raise ValueError("partials rr must asc")
        return v
class RiskSchema(BaseModel):
    risk_engine: RiskEngSchema; stop_loss: SLSchema; take_profit: TPSchema; validation: Dict[str,Any]
    @model_validator(mode="after")
    def book(self)->"RiskSchema":
        if self.take_profit.rr_ratio<self.validation.get("enforce_rr_min",1.5): raise ValueError("RR below min")
        if self.risk_engine.model=="StructureHybridSL" and self.stop_loss.type!="structure_hybrid": raise ValueError("Engine/SL mismatch")
        return self

@dataclass(frozen=True)
class MarketConfig:
    exchange_name: str; adapter: str; mapping: Dict[str,str]; symbols: List[str]; timeframe: str
    ohlcv_limit: int; ws_enabled: bool; event_topics: List[str]; credentials_fingerprint: str
    masked_api_key: str; testnet: bool; raw_secret: SecretStr=field(repr=False,compare=False)
    def get_secret(self)->SecretStr: return self.raw_secret
    def to_dict(self)->Dict[str,Any]:
        d=asdict(self); d.pop("raw_secret"); d["has_secret"]=True; return d

@dataclass(frozen=True)
class SignalConfig:
    model: str; prior_alpha: float; prior_beta: float; decay_factor: float
    min_probability: float; high_confidence: float; execution_threshold: float
    evidences: Dict[str,Dict[str,Any]]; require_min_evidences: int; weight_sum: float
    def get_enabled_evidences(self)->List[str]: return [k for k,v in self.evidences.items() if v["enabled"]]
    def get_bayesian_prior_mean(self)->float: return self.prior_alpha/(self.prior_alpha+self.prior_beta)

@dataclass(frozen=True)
class RiskConfig:
    model: str; max_risk_per_trade_pct: float; max_daily_loss_pct: float; max_open_positions: int
    sl_type: str; sl_hybrid_weights: Tuple[float,float]; sl_range: Tuple[float,float]; rr_ratio: float
    partials: List[Dict[str,float]]; trail_enabled: bool; leverage_max: int; account_size: float; breakeven_rr: float
    def calculate_position_size(self,entry:float,stop:float)->float:
        risk=self.account_size*self.max_risk_per_trade_pct/100.0
        d=abs(entry-stop)
        if d==0: raise ValueError("entry==stop")
        return risk/d
    def validate_trade(self,rr:float,sl_pct:float)->bool:
        lo,hi=self.sl_range; return rr>=1.5 and lo<=sl_pct<=hi

@dataclass(frozen=True)
class ApexConfig:
    market: MarketConfig; signal: SignalConfig; risk: RiskConfig; version: str="3.0.0-institutional"

class ApexConfigLoader:
    def __init__(self,config_dir:Optional[FP|str]=None)->None:
        self.config_dir=FP(config_dir) if config_dir else None; self._cache:Dict[str,BaseModel]={}
    def _resolve_yaml_str(self,name:str)->str:
        if self.config_dir:
            pp=self.config_dir/name
            if pp.exists(): return pp.read_text(encoding="utf-8")
        tmpl=CONFIG_TEMPLATES.get(name)
        if not tmpl: raise FileNotFoundError(name)
        return tmpl
    def _parse_yaml(self,content:str)->Dict[str,Any]:
        import os as _os
        data=yaml.safe_load(_os.path.expandvars(content))
        if not isinstance(data,dict): raise ValueError("YAML root must be mapping")
        return data
    def load_market(self,yaml_content:Optional[str]=None)->MarketConfig:
        data=self._parse_yaml(yaml_content or self._resolve_yaml_str("market.yaml"))
        try: v=MarketSchema(**data)
        except ValidationError as e: raise ValueError(f"Market validation Book II 2.6: {e}") from e
        self._cache["market"]=v; c=v.exchange.credentials
        return MarketConfig(v.exchange.name,v.exchange.adapter,v.exchange.mapping,v.symbols,v.timeframe,
            v.datafeed.ohlcv_limit,v.datafeed.ws_enabled,v.event_bus.topics,c.fingerprint(),c.masked(),c.testnet,raw_secret=c.api_secret)
    def load_signal(self,yaml_content:Optional[str]=None)->SignalConfig:
        data=self._parse_yaml(yaml_content or self._resolve_yaml_str("signal.yaml"))
        try: v=SignalSchema(**data)
        except ValidationError as e: raise ValueError(f"Signal validation: {e}") from e
        self._cache["signal"]=v; s=sum(x.weight for x in v.evidences.values() if x.enabled)
        ev={k:{"weight":x.weight,"enabled":x.enabled,"lookback":x.lookback} for k,x in v.evidences.items()}
        return SignalConfig(v.probability_engine.model,v.probability_engine.prior_alpha,v.probability_engine.prior_beta,
            v.probability_engine.decay_factor,v.thresholds.min_probability,v.thresholds.high_confidence,
            v.thresholds.execution_threshold,ev,v.aggregation.get("require_min_evidences",3),s)
    def load_risk(self,yaml_content:Optional[str]=None)->RiskConfig:
        data=self._parse_yaml(yaml_content or self._resolve_yaml_str("risk.yaml"))
        try: v=RiskSchema(**data)
        except ValidationError as e: raise ValueError(f"Risk validation Book II 2.6: {e}") from e
        self._cache["risk"]=v
        return RiskConfig(v.risk_engine.model,v.risk_engine.max_risk_per_trade_pct,v.risk_engine.max_daily_loss_pct,
            v.risk_engine.max_open_positions,v.stop_loss.type,(v.stop_loss.hybrid_weight_structure,v.stop_loss.hybrid_weight_atr),
            (v.stop_loss.min_sl_pct,v.stop_loss.max_sl_pct),v.take_profit.rr_ratio,
            [{"rr":p.rr,"pct_close":p.pct_close} for p in v.take_profit.partials],
            v.take_profit.trail_enabled,v.risk_engine.leverage_max,v.risk_engine.account_size_usdt,v.stop_loss.breakeven_trigger_rr)
    def load_all(self)->ApexConfig: return ApexConfig(self.load_market(),self.load_signal(),self.load_risk())
    def export_templates_to_dir(self,target:FP|str)->List[FP]:
        t=FP(target); t.mkdir(parents=True,exist_ok=True); out=[]
        for n,c in CONFIG_TEMPLATES.items():
            pp=t/n; pp.write_text(c.strip()+"\n",encoding="utf-8"); out.append(pp)
        return out

if __name__=="__main__":
    os.environ.setdefault("TOOBIT_API_KEY","test_key_1234567890")
    os.environ.setdefault("TOOBIT_API_SECRET","test_secret_0987654321")
    cfg=ApexConfigLoader().load_all()
    print(f"APEX {cfg.version} market={cfg.market.symbols} adapter={cfg.market.adapter} LONG->{cfg.market.mapping['LONG']}")
    print(f"  secret type={type(cfg.market.get_secret()).__name__} masked={cfg.market.masked_api_key} fp={cfg.market.credentials_fingerprint}")
    print(f"  signal {cfg.signal.model} evidences={len(cfg.signal.evidences)} sum={cfg.signal.weight_sum} prior_mean={cfg.signal.get_bayesian_prior_mean():.2f}")
    print(f"  risk {cfg.risk.model} sl={cfg.risk.sl_type} w={cfg.risk.sl_hybrid_weights} RR={cfg.risk.rr_ratio} size={cfg.risk.calculate_position_size(100,98.5):.2f}")
    assert isinstance(cfg.market.get_secret(),SecretStr); assert len(cfg.signal.evidences)==13; assert cfg.risk.sl_type=="structure_hybrid"
    print("All validations passed - Book II 2.6")

