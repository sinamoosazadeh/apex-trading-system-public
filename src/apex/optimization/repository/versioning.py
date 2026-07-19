
from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json

class VersionManager:
    """Versioning per blueprint - Immutable, no overwrite, rollback atomic safe auditable versioned"""
    def __init__(self, repository):
        self.repo = repository

    def get_active_version(self, symbol: str, timeframe: str, optimizer_type) -> str:
        base = self.repo._get_symbol_path(symbol, timeframe, optimizer_type)
        active_file = base / "active" / "ACTIVE_VERSION"
        if active_file.exists():
            return active_file.read_text().strip()
        return "none"

    def compare_versions(self, symbol: str, timeframe: str, optimizer_type, v1: str, v2: str) -> Dict[str, Any]:
        # Load both and compare metrics
        base = self.repo._get_symbol_path(symbol, timeframe, optimizer_type)
        versions_path = base / "versions"
        pkg1 = pkg2 = None
        for vdir in versions_path.iterdir():
            if v1 in vdir.name:
                try:
                    data = json.loads((vdir / "full_package.json").read_text())
                    pkg1 = data
                except: pass
            if v2 in vdir.name:
                try:
                    data = json.loads((vdir / "full_package.json").read_text())
                    pkg2 = data
                except: pass
        if not pkg1 or not pkg2:
            return {"error": "Version not found"}
        m1 = pkg1.get("metrics", {})
        m2 = pkg2.get("metrics", {})
        return {
            "v1": v1, "v2": v2,
            "v1_metrics": m1,
            "v2_metrics": m2,
            "improvement": (m2.get("composite_score",0) - m1.get("composite_score",0)) if isinstance(m1, dict) else 0,
            "v1_params_count": len(pkg1.get("parameters",{})),
            "v2_params_count": len(pkg2.get("parameters",{}))
        }
