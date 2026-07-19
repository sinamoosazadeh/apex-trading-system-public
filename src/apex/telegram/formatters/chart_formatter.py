
from __future__ import annotations
from typing import Dict, Any, List
import io

class ChartService:
    """Chart Generator per blueprint - Matplotlib"""
    def __init__(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            self.plt = plt
            self.available = True
        except:
            self.available = False
    
    def generate_equity_curve(self, equity_data: List[float]) -> bytes:
        if not self.available or not equity_data:
            return b""
        try:
            fig, ax = self.plt.subplots(figsize=(10,6))
            ax.plot(equity_data, color='green', linewidth=2)
            ax.set_title('Equity Curve')
            ax.set_xlabel('Trades')
            ax.set_ylabel('Equity')
            ax.grid(True, alpha=0.3)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            self.plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            return b""
    
    def generate_drawdown_chart(self, drawdown_data: List[float]) -> bytes:
        if not self.available or not drawdown_data:
            return b""
        try:
            fig, ax = self.plt.subplots(figsize=(10,6))
            ax.fill_between(range(len(drawdown_data)), drawdown_data, 0, color='red', alpha=0.3)
            ax.plot(drawdown_data, color='red')
            ax.set_title('Drawdown Chart')
            ax.set_xlabel('Trades')
            ax.set_ylabel('Drawdown %')
            ax.grid(True, alpha=0.3)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            self.plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except:
            return b""
    
    def generate_parameter_importance(self, importance: Dict[str, float]) -> bytes:
        if not self.available or not importance:
            return b""
        try:
            sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]
            if not sorted_items:
                return b""
            labels, values = zip(*sorted_items)
            fig, ax = self.plt.subplots(figsize=(12,8))
            ax.barh(range(len(labels)), values, color='skyblue')
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels)
            ax.set_title('Parameter Importance')
            ax.invert_yaxis()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            self.plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except:
            return b""
