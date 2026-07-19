
from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging, asyncio
from pathlib import Path

log = logging.getLogger(__name__)

class OptimizationController:
    """Optimization Controller per blueprint - Delegates to OptimizationOrchestrator"""
    
    def __init__(self, orchestrator=None, repository=None, app=None):
        self.orchestrator = orchestrator
        self.repository = repository
        self.app = app
        # Lazy load
        if not self.orchestrator:
            try:
                from ...optimization import get_orchestrator
                self.orchestrator = get_orchestrator()
                self.repository = self.orchestrator.repository
            except Exception as e:
                log.warning(f"Optimization orchestrator not available: {e}")
    
    async def run_optimization(self, symbol: str, timeframe: str, opt_type: str, trials: int, user_id: int) -> Dict[str, Any]:
        try:
            from ...optimization.models.optimization_state import OptimizerType
            opt_type_enum = OptimizerType.SIGNAL if "signal" in opt_type.lower() else OptimizerType.RISK_EXECUTION
            
            # Submit job
            job = self.orchestrator.submit_job(
                symbol=symbol,
                timeframe=timeframe,
                optimizer_type=opt_type_enum,
                n_trials=trials,
                priority=1
            )
            
            # Run async to not block telegram
            # In real implementation, this would be queued
            package = await asyncio.to_thread(
                self.orchestrator.run_sync,
                symbol, timeframe, opt_type_enum, trials
            )
            
            return {
                "job": job,
                "package": package,
                "status": "completed" if package else "failed"
            }
        except Exception as e:
            log.error(f"Optimization failed: {e}")
            raise
    
    def get_queue_status(self) -> Dict[str, Any]:
        if self.orchestrator:
            return self.orchestrator.get_status()
        return {"queue": {"queued": 0, "running": 0}, "total_jobs": 0}
    
    def list_versions(self, symbol: str, timeframe: str, opt_type: str) -> List[Dict[str, Any]]:
        if not self.repository:
            return []
        try:
            from ...optimization.models.optimization_state import OptimizerType
            opt_type_enum = OptimizerType.SIGNAL if "signal" in opt_type.lower() else OptimizerType.RISK_EXECUTION
            return self.repository.list_versions(symbol, timeframe, opt_type_enum)
        except Exception as e:
            log.error(f"List versions failed: {e}")
            return []
    
    def get_active(self, symbol: str, timeframe: str, opt_type: str):
        if not self.repository:
            return None
        try:
            from ...optimization.models.optimization_state import OptimizerType
            opt_type_enum = OptimizerType.SIGNAL if "signal" in opt_type.lower() else OptimizerType.RISK_EXECUTION
            return self.repository.get_active(symbol, timeframe, opt_type_enum)
        except Exception as e:
            log.error(f"Get active failed: {e}")
            return None
    
    def rollback(self, symbol: str, timeframe: str, opt_type: str, version: str) -> bool:
        if not self.repository:
            return False
        try:
            from ...optimization.models.optimization_state import OptimizerType
            opt_type_enum = OptimizerType.SIGNAL if "signal" in opt_type.lower() else OptimizerType.RISK_EXECUTION
            result = self.repository.rollback(symbol, timeframe, opt_type_enum, version)
            return result is not None
        except Exception as e:
            log.error(f"Rollback failed: {e}")
            return False
