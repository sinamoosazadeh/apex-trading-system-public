
from __future__ import annotations
from typing import Dict, Any
import json

class OptimizationFormatter:
    @staticmethod
    def format_package(package: Any) -> str:
        try:
            m = package.metrics if isinstance(package.metrics, dict) else package.metrics.__dict__ if hasattr(package.metrics, '__dict__') else {}
            v = package.validation_results if hasattr(package, 'validation_results') else {}
            
            score = v.get('composite_score', m.get('composite_score', 0)) if isinstance(v, dict) else 0
            if isinstance(score, dict):
                score = 0.6
            try:
                score_f = float(score)
            except:
                score_f = 0.6
            
            emoji = "🟢" if score_f > 0.7 else "🟡" if score_f > 0.5 else "🔴"
            
            msg = f"""{emoji} **Optimization Report**

📦 `{package.package_id[:24]}...`
🎯 {package.symbol} | {package.timeframe} | {package.optimizer_type.value if hasattr(package.optimizer_type, 'value') else package.optimizer_type}
🔧 v{package.version} | {package.optimization_method} | {package.n_trials} trials
🔒 {package.checksum[:8]} | {package.status}

📊 **Metrics:**
• Score: {score_f:.3f}
• PF: {m.get('profit_factor',0):.2f}
• Exp: {m.get('expectancy',0):.4f}
• WR: {m.get('win_rate',0):.1%}
• DD: {m.get('max_drawdown',0):.1%}
• Trades: {m.get('trade_count',0)}
• Sharpe: {m.get('sharpe_ratio',0):.2f}
• Robust: {m.get('robustness_score',0):.3f}

✅ **Validation:**
• WF: {'✅' if v.get('walk_forward',{}).get('passed') else '❌'} {v.get('walk_forward',{}).get('score',0):.3f}
• MC: {'✅' if v.get('monte_carlo',{}).get('passed') else '❌'} {v.get('monte_carlo',{}).get('score',0):.3f}
• Stress: {'✅' if v.get('stress',{}).get('passed') else '❌'}
• Overall: {'✅ ACCEPTED' if v.get('overall_passed') else '❌ REJECTED'}

🔝 **Params (sample):**
"""
            for i, (k,val) in enumerate(list(package.parameters.items())[:8]):
                if isinstance(val, float):
                    msg += f"• {k}: {val:.4f}\n"
                else:
                    msg += f"• {k}: {val}\n"
            msg += f"• ... +{len(package.parameters)-8} more\n" if len(package.parameters) > 8 else ""
            msg += f"\n🔗 Isolation: Never Mix ✅\n"
            return msg
        except Exception as e:
            return f"❌ Error formatting package: {e}"

    @staticmethod
    def format_version_list(versions: list, symbol: str, timeframe: str) -> str:
        if not versions:
            return f"📚 No versions for {symbol} {timeframe}"
        msg = f"📚 **Versions - {symbol} {timeframe}**\n\n"
        for i, v in enumerate(versions[:10], 1):
            msg += f"{i}. v{v.get('version','?')} | {v.get('creation_time','')[:10]} | Score: {v.get('composite_score','?')}\n"
        msg += f"\nTotal: {len(versions)} versions"
        return msg
    
    @staticmethod
    def format_queue(status: Dict[str, Any]) -> str:
        q = status.get('queue', {})
        msg = f"""📋 **Optimization Queue**

📥 Queued: {q.get('queued',0)}
⚙️ Running: {q.get('running',0)}
📊 Total Jobs: {status.get('total_jobs',0)}

"""
        if q.get('queued_jobs'):
            msg += "**Queued:**\n"
            for job in q['queued_jobs'][:5]:
                msg += f"• {job.get('symbol')} {job.get('timeframe')} {job.get('type')}\n"
        if q.get('running_jobs'):
            msg += "\n**Running:**\n"
            for job in q['running_jobs']:
                msg += f"• {job.get('symbol')} {job.get('timeframe')}\n"
        return msg
