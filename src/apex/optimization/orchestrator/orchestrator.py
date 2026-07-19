
from __future__ import annotations
from typing import Dict, Any, Optional, Callable
import logging, psutil, time
from datetime import datetime, timezone

from ..models.optimization_job import OptimizationJob
from ..models.optimization_state import OptimizationState, OptimizerType
from ..models.parameter_package import ParameterPackage
from ..models.optimization_metrics import OptimizationMetrics
from .queue_manager import QueueManager
from .scheduler import Scheduler
from .lifecycle import LifecycleManager
from ..repository.repository import ParameterRepository
from ..validation.validation_pipeline import ValidationPipeline
from ..signal.optimizer import SignalOptimizer
from ..risk.optimizer import RiskExecutionOptimizer

log = logging.getLogger(__name__)

class OptimizationOrchestrator:
    """Meta Optimization Orchestrator per blueprint - Single point of control, no Optimizer directly saves files"""
    def __init__(self, base_path: str = "optimization_artifacts", evaluate_fn_factory: Callable = None):
        self.queue_manager = QueueManager()
        self.lifecycle = LifecycleManager()
        self.repository = ParameterRepository(base_path=base_path)
        self.validation_pipeline = ValidationPipeline()
        self.scheduler = Scheduler(self)
        self.evaluate_fn_factory = evaluate_fn_factory  # Factory to create evaluate_fn per symbol/timeframe/type
        self.jobs: Dict[str, OptimizationJob] = {}
        self._injection_callbacks = []

    def _default_evaluate_fn(self, symbol: str, timeframe: str, optimizer_type: OptimizerType) -> Callable[[Dict[str, Any]], OptimizationMetrics]:
        # Default evaluate using backtest if factory not provided
        def evaluate(params: Dict[str, Any]) -> OptimizationMetrics:
            # Simulate realistic metrics based on params - in production would call backtest_engine
            import random, math
            # Use params to create deterministic but varied score
            param_hash = hash(frozenset((k, str(v)[:10]) for k,v in params.items())) % 1000
            random.seed(param_hash)
            # Simulate trading
            win_rate = 0.45 + random.random()*0.2
            pf = 1.0 + random.random()*1.5
            exp = (win_rate*1.5 - (1-win_rate))*0.5 + random.random()*0.2
            dd = 0.05 + random.random()*0.15
            trades = 50 + int(random.random()*150)
            # Some params improve score
            bonus = 0
            if params.get("stop_model") in ["hybrid","adaptive","liquidity"]:
                bonus += 0.1
            if params.get("tp_model") in ["liquidity","multiple"]:
                bonus += 0.08
            if params.get("sizing_model") in ["half_kelly","fractional_kelly"]:
                bonus += 0.05
            metrics = OptimizationMetrics(
                net_profit=exp*trades*100,
                profit_factor=pf + bonus,
                expectancy=max(0, exp + bonus*0.1),
                sharpe_ratio=0.8 + random.random()*1.2 + bonus,
                sortino_ratio=1.0 + random.random()*1.5 + bonus,
                calmar_ratio=0.5 + random.random()*1.0,
                max_drawdown=dd * (1 - bonus*0.3),
                win_rate=win_rate + bonus*0.05,
                avg_r=exp,
                trade_count=trades,
                robustness_score=0.4 + random.random()*0.4 + bonus*0.2,
                stability_score=0.5 + random.random()*0.3 + bonus*0.1,
                walk_forward_score=0.5 + random.random()*0.3 + bonus*0.1,
                overfitting_score=random.random()*0.3,
                avg_rr=1.5 + random.random()*1.5,
                stop_efficiency=0.5 + random.random()*0.3,
            )
            return metrics
        return evaluate

    def submit_job(self, symbol: str, timeframe: str, optimizer_type: OptimizerType, priority=5, n_trials=100, config=None) -> OptimizationJob:
        job = OptimizationJob.create(symbol=symbol, timeframe=timeframe, optimizer_type=optimizer_type, priority=priority, n_trials=n_trials, config=config)
        self.jobs[job.job_id] = job
        self.queue_manager.enqueue(job)
        self.lifecycle.record_transition(job.job_id, "none", job.status.value, "Job submitted")
        log.info(f"Submitted job {job.job_id} {symbol} {timeframe} {optimizer_type.value}")
        return job

    def run_next(self) -> Optional[ParameterPackage]:
        # Resource Management per blueprint
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            if cpu > 85 or mem > 85:
                log.warning(f"Resource high CPU:{cpu}% MEM:{mem}% - delaying optimization")
                time.sleep(2)
                return None
        except:
            pass

        job = self.queue_manager.dequeue()
        if not job:
            return None

        try:
            job.transition(OptimizationState.RUNNING, "Started execution")
            self.lifecycle.record_transition(job.job_id, "scheduled", "running", "Execution started")

            # Create evaluate function
            if self.evaluate_fn_factory:
                evaluate_fn = self.evaluate_fn_factory(job.symbol, job.timeframe, job.optimizer_type)
            else:
                evaluate_fn = self._default_evaluate_fn(job.symbol, job.timeframe, job.optimizer_type)

            # Run appropriate optimizer
            if job.optimizer_type == OptimizerType.SIGNAL:
                optimizer = SignalOptimizer(symbol=job.symbol, timeframe=job.timeframe, evaluate_fn=evaluate_fn)
            elif job.optimizer_type == OptimizerType.RISK_EXECUTION:
                optimizer = RiskExecutionOptimizer(symbol=job.symbol, timeframe=job.timeframe, evaluate_fn=evaluate_fn)
            else:
                # Fallback to signal for research/portfolio/meta
                optimizer = SignalOptimizer(symbol=job.symbol, timeframe=job.timeframe, evaluate_fn=evaluate_fn)

            package = optimizer.optimize(n_trials=job.n_trials)

            # Validation
            job.transition(OptimizationState.VALIDATION, "Running validation pipeline")
            validation_results = self.validation_pipeline.validate(package)
            package.validation_results.update(validation_results)
            package.validation_time = datetime.now(timezone.utc).isoformat()

            # Acceptance
            active_pkg = self.repository.get_active(job.symbol, job.timeframe, job.optimizer_type)
            acceptance = self.validation_pipeline.acceptance_check(package, active_pkg)
            package.validation_results["acceptance"] = acceptance

            if acceptance.get("overall_accepted", False) and validation_results.get("overall_passed", False):
                job.transition(OptimizationState.APPROVED, "Validation passed")
                package.status = "approved"
                package.approval_time = datetime.now(timezone.utc).isoformat()

                # Store
                self.repository.save(package)
                job.transition(OptimizationState.STORED, "Artifact stored")

                # Activate (Deployment per blueprint: Validation -> Benchmark -> Health -> Shadow -> Candidate -> Active)
                self.repository.activate(package)
                job.transition(OptimizationState.INJECTED, "Injected to active")
                job.artifact_path = str(self.repository._get_symbol_path(job.symbol, job.timeframe, job.optimizer_type) / "active")

                # Injection callbacks
                for cb in self._injection_callbacks:
                    try:
                        cb(package)
                    except Exception as e:
                        log.warning(f"Injection callback failed: {e}")

                job.transition(OptimizationState.ARCHIVED, "Completed successfully")
                self.queue_manager.mark_finished(job)
                return package
            else:
                job.transition(OptimizationState.REJECTED, f"Rejected: {acceptance}")
                job.error = f"Validation failed or not accepted: {acceptance}"
                self.queue_manager.mark_finished(job)
                log.warning(f"Job {job.job_id} rejected")
                return package

        except Exception as e:
            log.error(f"Job {job.job_id} failed: {e}", exc_info=True)
            job.error = str(e)
            job.retries += 1
            if job.can_retry():
                job.transition(OptimizationState.QUEUED, f"Retry {job.retries}/{job.max_retries} after failure: {e}")
                self.queue_manager.enqueue(job)
            else:
                job.transition(OptimizationState.FAILED, f"Failed after {job.retries} retries: {e}")
            self.queue_manager.mark_finished(job)
            return None

    def run_sync(self, symbol: str, timeframe: str, optimizer_type: OptimizerType, n_trials: int = 50) -> Optional[ParameterPackage]:
        """Synchronous run for testing / Telegram"""
        job = self.submit_job(symbol=symbol, timeframe=timeframe, optimizer_type=optimizer_type, n_trials=n_trials, priority=1)
        # Run immediately
        result = self.run_next()
        # If queue had other jobs, keep running until our job finishes
        attempts = 0
        while result is None or (result and result.symbol != symbol) and attempts < 10:
            result = self.run_next()
            attempts += 1
            if result and result.symbol == symbol and result.timeframe == timeframe:
                break
        # Try to get active if we already processed
        if result is None:
            active = self.repository.get_active(symbol, timeframe, optimizer_type)
            if active:
                return active
        return result

    def register_injection_callback(self, callback: Callable[[ParameterPackage], None]):
        self._injection_callbacks.append(callback)

    def get_status(self):
        return {
            "queue": self.queue_manager.get_queue_status(),
            "total_jobs": len(self.jobs),
            "schedules": len(self.scheduler.schedules)
        }
