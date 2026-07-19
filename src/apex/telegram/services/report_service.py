
from __future__ import annotations
from typing import Dict, Any, List
import json, csv, io
from datetime import datetime, timezone
from pathlib import Path

class ReportService:
    """Report Export Service per blueprint - PDF, CSV, Excel, JSON"""
    
    def __init__(self, base_path: str = "reports"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def export_backtest_csv(self, trades: List[Dict[str, Any]], symbol: str, timeframe: str) -> bytes:
        output = io.StringIO()
        if not trades:
            return b""
        writer = csv.DictWriter(output, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
        return output.getvalue().encode()
    
    def export_backtest_json(self, data: Dict[str, Any]) -> bytes:
        return json.dumps(data, indent=2, default=str).encode()
    
    def export_optimization_report(self, package: Any, format: str = "json") -> bytes:
        try:
            from ..formatters.optimization_formatter import OptimizationFormatter
            if format == "json":
                return json.dumps({
                    "package_id": package.package_id,
                    "version": package.version,
                    "symbol": package.symbol,
                    "timeframe": package.timeframe,
                    "parameters": package.parameters,
                    "metrics": package.metrics if isinstance(package.metrics, dict) else package.metrics.__dict__ if hasattr(package.metrics, '__dict__') else {},
                    "validation": package.validation_results,
                    "checksum": package.checksum,
                    "creation_time": package.creation_time
                }, indent=2, default=str).encode()
            elif format == "csv":
                # Parameters as CSV
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Parameter", "Value"])
                for k,v in package.parameters.items():
                    writer.writerow([k, v])
                return output.getvalue().encode()
        except Exception as e:
            return f"Error: {e}".encode()
        return b""
    
    def generate_pdf_report(self, data: Dict[str, Any]) -> bytes:
        """Simple PDF generation - in production use reportlab"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=letter)
            c.drawString(100, 750, f"APEX Report - {data.get('symbol','')} {data.get('timeframe','')}")
            c.drawString(100, 730, f"Generated: {datetime.now(timezone.utc).isoformat()}")
            y = 710
            for k,v in data.items():
                if y < 50:
                    c.showPage()
                    y = 750
                c.drawString(100, y, f"{k}: {str(v)[:80]}")
                y -= 20
            c.save()
            buf.seek(0)
            return buf.getvalue()
        except:
            # Fallback: return JSON as PDF placeholder
            return self.export_backtest_json(data)
