
import pytest
from apex.optimization import get_orchestrator, OptimizerType
from apex.optimization.models.parameter_package import ParameterPackage

def test_orchestrator_creation():
    orch = get_orchestrator(base_path="/tmp/test_opt")
    assert orch is not None

def test_signal_optimizer_isolation():
    orch = get_orchestrator(base_path="/tmp/test_opt_isolation")
    pkg = orch.run_sync('BTC-SWAP-USDT','1h',OptimizerType.SIGNAL,n_trials=5)
    assert pkg is not None
    assert pkg.is_valid_for('BTC-SWAP-USDT','1h')
    assert not pkg.is_valid_for('ETH-SWAP-USDT','1h'), "Never Mix Coins - must fail"
    assert not pkg.is_valid_for('BTC-SWAP-USDT','4h'), "Never Mix Timeframes - must fail"

def test_risk_optimizer():
    orch = get_orchestrator(base_path="/tmp/test_opt_risk")
    pkg = orch.run_sync('BTC-SWAP-USDT','1h',OptimizerType.RISK_EXECUTION,n_trials=5)
    assert pkg is not None
    assert "stop_model" in pkg.parameters
    assert "tp_model" in pkg.parameters
    assert "sizing_model" in pkg.parameters

def test_parameter_package_checksum():
    pkg = ParameterPackage.create_new("BTC-SWAP-USDT","1h",OptimizerType.SIGNAL,{"w_momentum":0.1})
    assert pkg.checksum
    assert len(pkg.checksum) == 16
    assert pkg.compute_checksum() == pkg.checksum

def test_repository_versioning():
    from apex.optimization.repository.repository import ParameterRepository
    repo = ParameterRepository(base_path="/tmp/test_repo")
    pkg = ParameterPackage.create_new("BTC-SWAP-USDT","1h",OptimizerType.SIGNAL,{"test":1})
    path = repo.save(pkg)
    assert path.exists()
    repo.activate(pkg)
    active = repo.get_active("BTC-SWAP-USDT","1h",OptimizerType.SIGNAL)
    assert active is not None
    assert active.package_id == pkg.package_id
