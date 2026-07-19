
from __future__ import annotations
from typing import Dict, Any
from ..models.parameter_package import ParameterPackage

class ReportGenerator:
    """Machine-Readable and Human-Readable reports per blueprint"""
    def generate(self, package: ParameterPackage) -> Dict[str, Any]:
        return {
            "optimization_report": {
                "package_id": package.package_id,
                "version": package.version,
                "symbol": package.symbol,
                "timeframe": package.timeframe,
                "optimizer_type": package.optimizer_type.value,
                "creation_time": package.creation_time,
                "method": package.optimization_method,
                "n_trials": package.n_trials,
                "checksum": package.checksum
            },
            "parameter_report": {
                "parameters": package.parameters,
                "total_params": len(package.parameters)
            },
            "validation_report": package.validation_results,
            "metrics_report": package.metrics,
            "deployment_report": {
                "status": package.status,
                "validation_time": package.validation_time,
                "approval_time": package.approval_time,
                "expiration_time": package.expiration_time,
                "parent_version": package.parent_version
            },
            "change_log": package.changelog or f"Optimized {package.symbol} {package.timeframe} with {package.n_trials} trials"
        }

    def to_markdown(self, package: ParameterPackage) -> str:
        m = package.metrics if isinstance(package.metrics, dict) else {}
        if hasattr(package.metrics, "__dict__"):
            m = package.metrics.__dict__
        md = f"""# Optimization Report
**Package:** {package.package_id}
**Symbol:** {package.symbol} | **Timeframe:** {package.timeframe} | **Type:** {package.optimizer_type.value}
**Version:** {package.version} | **Method:** {package.optimization_method} | **Trials:** {package.n_trials}
**Status:** {package.status} | **Checksum:** {package.checksum}

## Metrics
- Composite Score: {package.validation_results.get('composite_score', m.get('composite_score', 'N/A'))}
- Profit Factor: {m.get('profit_factor', 'N/A')}
- Expectancy: {m.get('expectancy', 'N/A')}
- Win Rate: {m.get('win_rate', 'N/A')}
- Max DD: {m.get('max_drawdown', 'N/A')}
- Trades: {m.get('trade_count', 'N/A')}
- Sharpe: {m.get('sharpe_ratio', 'N/A')}
- Robustness: {m.get('robustness_score', 'N/A')}

## Validation
- Walk Forward: {package.validation_results.get('walk_forward', {}).get('passed', 'N/A')} Score: {package.validation_results.get('walk_forward', {}).get('score', 'N/A')}
- Monte Carlo: {package.validation_results.get('monte_carlo', {}).get('passed', 'N/A')} Score: {package.validation_results.get('monte_carlo', {}).get('score', 'N/A')}
- Stress: {package.validation_results.get('stress', {}).get('passed', 'N/A')}
- Overall: {package.validation_results.get('overall_passed', 'N/A')}

## Top Parameters
"""
        for k,v in list(package.parameters.items())[:15]:
            md += f"- {k}: {v}\n"
        if len(package.parameters) > 15:
            md += f"- ... and {len(package.parameters)-15} more\n"
        return md
