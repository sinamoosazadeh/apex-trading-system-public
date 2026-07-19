
from __future__ import annotations
from .models.optimization_state import OptimizationState, OptimizerType
from .models.parameter_package import ParameterPackage
from .models.optimization_job import OptimizationJob
from .models.optimization_metrics import OptimizationMetrics
from .models.optimization_result import OptimizationResult
from .orchestrator.orchestrator import OptimizationOrchestrator
from .repository.repository import ParameterRepository
from .injection.injector import ParameterInjector
from .validation.validation_pipeline import ValidationPipeline

__all__ = [
    "OptimizationState", "OptimizerType",
    "ParameterPackage", "OptimizationJob", "OptimizationMetrics", "OptimizationResult",
    "OptimizationOrchestrator", "ParameterRepository", "ParameterInjector", "ValidationPipeline"
]

_global_orchestrator = None

def get_orchestrator(base_path: str = "optimization_artifacts", evaluate_fn_factory=None) -> OptimizationOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = OptimizationOrchestrator(base_path=base_path, evaluate_fn_factory=evaluate_fn_factory)
    return _global_orchestrator

def get_repository(base_path: str = "optimization_artifacts") -> ParameterRepository:
    return ParameterRepository(base_path=base_path)

def get_injector(base_path: str = "optimization_artifacts") -> ParameterInjector:
    repo = get_repository(base_path)
    return ParameterInjector(repository=repo)
