
from __future__ import annotations
from pathlib import Path
import json, shutil, hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from ..models.parameter_package import ParameterPackage
from ..models.optimization_state import OptimizerType

log = logging.getLogger(__name__)

class ParameterRepository:
    """Hierarchical storage per blueprint: optimization/signal/BTCUSDT/1h/versions/active/archive/metadata - No overwrite, immutable"""
    def __init__(self, base_path: str = "optimization_artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_symbol_path(self, symbol: str, timeframe: str, optimizer_type: OptimizerType) -> Path:
        # Clean symbol: BTC-SWAP-USDT -> BTCUSDT
        clean_symbol = symbol.replace("-","").replace("_","")
        p = self.base_path / optimizer_type.value / clean_symbol / timeframe
        p.mkdir(parents=True, exist_ok=True)
        (p / "versions").mkdir(exist_ok=True)
        (p / "active").mkdir(exist_ok=True)
        (p / "archive").mkdir(exist_ok=True)
        (p / "metadata").mkdir(exist_ok=True)
        return p

    def save(self, package: ParameterPackage) -> Path:
        # Never overwrite - immutable
        base = self._get_symbol_path(package.symbol, package.timeframe, package.optimizer_type)
        version_path = base / "versions" / f"{package.version}_{package.package_id}"
        version_path.mkdir(parents=True, exist_ok=True)

        # Write artifact per blueprint
        (version_path / "optimized_parameters.json").write_text(json.dumps(package.parameters, indent=2, default=str))
        (version_path / "metadata.json").write_text(json.dumps({
            "package_id": package.package_id,
            "version": package.version,
            "symbol": package.symbol,
            "timeframe": package.timeframe,
            "optimizer_type": package.optimizer_type.value,
            "market_regime": package.market_regime,
            "optimizer_version": package.optimizer_version,
            "blueprint_version": package.blueprint_version,
            "git_revision": package.git_revision,
            "dataset_hash": package.dataset_hash,
            "configuration_hash": package.configuration_hash,
            "creation_time": package.creation_time,
            "validation_time": package.validation_time,
            "approval_time": package.approval_time,
            "expiration_time": package.expiration_time,
            "checksum": package.checksum,
            "status": package.status,
            "parent_version": package.parent_version,
            "optimization_method": package.optimization_method,
            "n_trials": package.n_trials,
            "changelog": package.changelog
        }, indent=2))
        (version_path / "validation.json").write_text(json.dumps(package.validation_results, indent=2, default=str))
        (version_path / "metrics.json").write_text(json.dumps(package.metrics, indent=2, default=str))
        (version_path / "history.json").write_text(json.dumps(package.history[-100:] if len(package.history)>100 else package.history, indent=2, default=str))  # last 100
        # Signature
        content = (version_path / "optimized_parameters.json").read_text() + package.version
        sha = hashlib.sha256(content.encode()).hexdigest()
        (version_path / "signature.sha256").write_text(sha)
        # Full package
        (version_path / "full_package.json").write_text(json.dumps(package.to_dict(), indent=2, default=str))

        log.info(f"Saved artifact {package.package_id} version {package.version} to {version_path}")
        return version_path

    def activate(self, package: ParameterPackage) -> Path:
        base = self._get_symbol_path(package.symbol, package.timeframe, package.optimizer_type)
        version_path = base / "versions" / f"{package.version}_{package.package_id}"
        active_path = base / "active"
        # Clear active and copy new
        for f in active_path.glob("*"):
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)
        # Copy version to active
        if version_path.exists():
            for item in version_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, active_path / item.name)
                else:
                    shutil.copytree(item, active_path / item.name, dirs_exist_ok=True)
        # Update status
        package.status = "active"
        (active_path / "ACTIVE_VERSION").write_text(f"{package.version}_{package.package_id}")
        return active_path

    def get_active(self, symbol: str, timeframe: str, optimizer_type: OptimizerType) -> Optional[ParameterPackage]:
        base = self._get_symbol_path(symbol, timeframe, optimizer_type)
        active_path = base / "active"
        full_pkg_file = active_path / "full_package.json"
        if not full_pkg_file.exists():
            return None
        try:
            data = json.loads(full_pkg_file.read_text())
            # Verify signature
            sig_file = active_path / "signature.sha256"
            param_file = active_path / "optimized_parameters.json"
            if sig_file.exists() and param_file.exists():
                content = param_file.read_text() + data.get("version","")
                expected_sha = hashlib.sha256(content.encode()).hexdigest()
                actual_sha = sig_file.read_text().strip()
                if expected_sha != actual_sha:
                    log.warning(f"Signature mismatch for {symbol} {timeframe} {optimizer_type.value} - artifact may be corrupted")
                    return None
            # Reconstruct package
            pkg = ParameterPackage(
                package_id=data.get("package_id",""),
                version=data.get("version",""),
                symbol=data.get("symbol",symbol),
                timeframe=data.get("timeframe",timeframe),
                optimizer_type=optimizer_type,
                parameters=data.get("parameters",{}),
                metrics=data.get("metrics"),
                validation_results=data.get("validation_results",{}),
                checksum=data.get("checksum",""),
                status="active",
                market_regime=data.get("market_regime","all"),
                optimizer_version=data.get("optimizer_version","1.0.0"),
                blueprint_version=data.get("blueprint_version","APEX v4"),
                creation_time=data.get("creation_time"),
                history=data.get("history",[])
            )
            # Isolation check - Never Mix Coins/Timeframes
            if not pkg.is_valid_for(symbol, timeframe):
                log.error(f"Isolation violation: package {pkg.symbol}/{pkg.timeframe} requested for {symbol}/{timeframe}")
                return None
            return pkg
        except Exception as e:
            log.error(f"Failed to load active package {symbol} {timeframe}: {e}")
            return None

    def list_versions(self, symbol: str, timeframe: str, optimizer_type: OptimizerType) -> List[Dict[str, Any]]:
        base = self._get_symbol_path(symbol, timeframe, optimizer_type)
        versions_path = base / "versions"
        versions = []
        for vdir in versions_path.iterdir():
            if vdir.is_dir():
                meta_file = vdir / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        versions.append(meta)
                    except:
                        pass
        return sorted(versions, key=lambda x: x.get("creation_time",""), reverse=True)

    def rollback(self, symbol: str, timeframe: str, optimizer_type: OptimizerType, target_version: str) -> Optional[ParameterPackage]:
        base = self._get_symbol_path(symbol, timeframe, optimizer_type)
        versions_path = base / "versions"
        for vdir in versions_path.iterdir():
            if target_version in vdir.name:
                full_pkg_file = vdir / "full_package.json"
                if full_pkg_file.exists():
                    data = json.loads(full_pkg_file.read_text())
                    pkg = ParameterPackage(
                        package_id=data.get("package_id",""),
                        version=data.get("version",""),
                        symbol=data.get("symbol",symbol),
                        timeframe=data.get("timeframe",timeframe),
                        optimizer_type=optimizer_type,
                        parameters=data.get("parameters",{}),
                        metrics=data.get("metrics"),
                        validation_results=data.get("validation_results",{}),
                        checksum=data.get("checksum",""),
                        status="active"
                    )
                    self.activate(pkg)
                    log.info(f"Rolled back {symbol} {timeframe} to {target_version}")
                    return pkg
        return None
