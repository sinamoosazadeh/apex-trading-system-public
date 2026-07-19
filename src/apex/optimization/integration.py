
from __future__ import annotations
import logging

log = logging.getLogger(__name__)

def integrate_optimization_system(app):
    """Integrate optimization subsystem into existing bootstrap without breaking - Adapter pattern per blueprint"""
    try:
        from . import get_orchestrator, get_repository, get_injector
        from .models.optimization_state import OptimizerType

        # Initialize repository and orchestrator
        orchestrator = get_orchestrator(base_path="optimization_artifacts")
        repository = get_repository(base_path="optimization_artifacts")
        injector = get_injector(base_path="optimization_artifacts")

        # Attach to app
        app.optimization_orchestrator = orchestrator
        app.optimization_repository = repository
        app.optimization_injector = injector

        # Try to inject active params into engines if available
        for symbol in getattr(app, "symbols", [])[:3]:  # Load first 3 symbols to avoid slowdown
            for tf in getattr(app, "timeframes", ["1h"])[:2]:
                try:
                    if hasattr(app, "probability_engine"):
                        injector.inject_to_probability_engine(app.probability_engine, symbol, tf)
                    if hasattr(app, "risk_engine"):
                        injector.inject_to_risk_engine(app.risk_engine, symbol, tf)
                except Exception as e:
                    log.debug(f"Injection for {symbol} {tf} skipped: {e}")

        # Register injection callback for future optimizations
        def on_new_package(package):
            log.info(f"New optimization package activated: {package.package_id} {package.symbol} {package.timeframe}")
            # Auto-inject if matches current symbol
            try:
                if hasattr(app, "probability_engine") and package.optimizer_type == OptimizerType.SIGNAL:
                    injector.inject_to_probability_engine(app.probability_engine, package.symbol, package.timeframe)
                if hasattr(app, "risk_engine") and package.optimizer_type == OptimizerType.RISK_EXECUTION:
                    injector.inject_to_risk_engine(app.risk_engine, package.symbol, package.timeframe)
            except Exception as e:
                log.warning(f"Auto-injection failed: {e}")

        orchestrator.register_injection_callback(on_new_package)

        log.info("✅ Optimization subsystem integrated - Signal + Risk Execution + Orchestrator + Validation + Repository + Injection")
        return True
    except Exception as e:
        log.warning(f"Optimization integration failed (non-critical): {e}")
        return False
