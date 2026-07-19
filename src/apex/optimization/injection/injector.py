
from __future__ import annotations
from typing import Dict, Any, Optional
import logging

from ..models.parameter_package import ParameterPackage
from ..models.optimization_state import OptimizerType
from ..repository.repository import ParameterRepository

log = logging.getLogger(__name__)

class ParameterInjector:
    """Injection Layer per blueprint - Only layer allowed to inject params into engines"""
    def __init__(self, repository: ParameterRepository):
        self.repository = repository
        self.cache: Dict[str, ParameterPackage] = {}

    def load_for(self, symbol: str, timeframe: str, optimizer_type: OptimizerType) -> Optional[ParameterPackage]:
        cache_key = f"{symbol}_{timeframe}_{optimizer_type.value}"
        # Check cache
        if cache_key in self.cache:
            pkg = self.cache[cache_key]
            # Verify still valid for symbol/timeframe - Never Mix
            if pkg.is_valid_for(symbol, timeframe):
                return pkg
            else:
                log.error(f"Cache isolation violation for {cache_key}")
                del self.cache[cache_key]

        pkg = self.repository.get_active(symbol, timeframe, optimizer_type)
        if pkg:
            # Isolation check
            if not pkg.is_valid_for(symbol, timeframe):
                log.error(f"Isolation violation: package {pkg.symbol}/{pkg.timeframe} requested for {symbol}/{timeframe}")
                return None
            self.cache[cache_key] = pkg
            log.info(f"Injected {optimizer_type.value} params for {symbol} {timeframe} version {pkg.version}")
        return pkg

    def inject_to_probability_engine(self, prob_engine, symbol: str, timeframe: str) -> bool:
        pkg = self.load_for(symbol, timeframe, OptimizerType.SIGNAL)
        if not pkg:
            return False
        try:
            # Inject evidence weights
            for k,v in pkg.parameters.items():
                if k.startswith("w_"):
                    if hasattr(prob_engine, "evidence_weights"):
                        prob_engine.evidence_weights[k[2:]] = v
                    elif hasattr(prob_engine, "weights"):
                        prob_engine.weights[k[2:]] = v
            # Inject thresholds
            for thresh_key in ["confidence_threshold","min_probability","decision_threshold_long","decision_threshold_short","bayesian_prior"]:
                if thresh_key in pkg.parameters and hasattr(prob_engine, thresh_key):
                    setattr(prob_engine, thresh_key, pkg.parameters[thresh_key])
            log.info(f"Injected signal params to ProbabilityEngine for {symbol} {timeframe}")
            return True
        except Exception as e:
            log.error(f"Injection to ProbabilityEngine failed: {e}")
            return False

    def inject_to_risk_engine(self, risk_engine, symbol: str, timeframe: str) -> bool:
        pkg = self.load_for(symbol, timeframe, OptimizerType.RISK_EXECUTION)
        if not pkg:
            return False
        try:
            # Inject risk params
            for k in ["risk_per_trade","atr_stop_multiplier","be_trigger_rr","max_daily_risk","max_symbol_exposure","sizing_model","stop_model","tp_model"]:
                if k in pkg.parameters:
                    if hasattr(risk_engine, k):
                        setattr(risk_engine, k, pkg.parameters[k])
                    elif hasattr(risk_engine, "config") and isinstance(risk_engine.config, dict):
                        risk_engine.config[k] = pkg.parameters[k]
            # Store full package for advanced usage
            if hasattr(risk_engine, "active_optimization_package"):
                risk_engine.active_optimization_package = pkg
            log.info(f"Injected risk params to RiskEngine for {symbol} {timeframe}")
            return True
        except Exception as e:
            log.error(f"Injection to RiskEngine failed: {e}")
            return False
