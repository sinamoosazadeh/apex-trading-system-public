
#!/usr/bin/env python3
"""APEX Project Full Audit - Crypto-Only - Check missing, skeleton, unconnected"""
import os
import pathlib
import ast

root = pathlib.Path("/data/data/com.termux/files/home/apex/src/apex")
if not root.exists():
    root = pathlib.Path("./src/apex")

print("="*80)
print("🔍 APEX PROJECT FULL AUDIT - CRYPTO-ONLY")
print("="*80)

# Expected structure per blueprints
expected_modules = {
    "core": ["events.py", "types/enums.py", "types/__init__.py"],
    "domain": ["market.py", "trading.py", "knowledge.py", "contracts.py"],
    "features": [
        "feature_store.py", "primitives.py", "structure.py", "regime_engine.py",
        "ict_engine.py", "order_flow_engine.py", "liquidity_engine.py",
        "smt_engine.py", "evidence_engine.py"
    ],
    "engines": [
        "probability_engine.py", "decision_engine.py", "risk_engine.py",
        "portfolio_engine.py", "execution_engine.py", "governance.py"
    ],
    "infrastructure": [
        "exchanges/toobit_adapter.py", "exchanges/toobit_ws.py",
        "telegram/bot.py", "telegram/handlers.py"
    ],
    "backtest": ["backtest_engine.py", "telegram_menu.py"],
    "security": ["vault.py", "contracts.py", "secure_config.py"],
    "monitoring": ["structured_logger.py", "metrics_engine.py", "health_monitor.py"],
    "research": ["knowledge_base.py", "research_engine.py"],
    "application": ["bootstrap.py", "cli.py"]
}

skeleton_files = []
missing_files = []
empty_files = []
implemented_files = []
large_files = []

for module, files in expected_modules.items():
    mod_path = root / module
    if not mod_path.exists():
        print(f"❌ Missing module: {module}/")
        missing_files.extend([f"{module}/{f}" for f in files])
        continue
    for f in files:
        fp = mod_path / f
        if not fp.exists():
            missing_files.append(f"{module}/{f}")
        else:
            try:
                content = fp.read_text()
                lines = len(content.splitlines())
                if lines < 10:
                    skeleton_files.append(f"{module}/{f} ({lines} lines)")
                elif lines < 30:
                    empty_files.append(f"{module}/{f} ({lines} lines - possibly skeleton)")
                else:
                    implemented_files.append(f"{module}/{f} ({lines} lines)")
                    if lines > 500:
                        large_files.append(f"{module}/{f} ({lines} lines)")
            except:
                missing_files.append(f"{module}/{f} (unreadable)")

print("\n📁 MODULE AUDIT:")
for module in expected_modules:
    mod_path = root / module
    exists = "✅" if mod_path.exists() else "❌"
    print(f"{exists} {module}/")

print(f"\n❌ MISSING FILES ({len(missing_files)}):")
for f in missing_files[:30]:
    print(f"  - {f}")

print(f"\n⚠️ SKELETON/EMPTY FILES ({len(skeleton_files)+len(empty_files)}):")
for f in skeleton_files + empty_files:
    print(f"  - {f}")

print(f"\n✅ IMPLEMENTED FILES ({len(implemented_files)}):")
for f in implemented_files[:50]:
    print(f"  - {f}")

print(f"\n📊 LARGE FILES (>500 lines):")
for f in large_files:
    print(f"  - {f}")

# Check connectivity - imports
print("\n" + "="*80)
print("🔗 CONNECTIVITY AUDIT - Are modules connected in bootstrap?")
print("="*80)

bootstrap = root / "application" / "bootstrap.py"
if bootstrap.exists():
    b_content = bootstrap.read_text()
    checks = [
        ("PrimitiveFeatures", "primitive_features" in b_content.lower()),
        ("RegimeEngine", "regime_engine" in b_content.lower()),
        ("ICTEngine", "ict_engine" in b_content.lower()),
        ("OrderFlow", "order_flow" in b_content.lower()),
        ("Liquidity", "liquidity" in b_content.lower()),
        ("SMT", "smt" in b_content.lower()),
        ("EvidenceEngine", "evidence_engine" in b_content.lower()),
        ("ProbabilityEngine", "probability_engine" in b_content.lower()),
        ("DecisionEngine", "decision_engine" in b_content.lower()),
        ("RiskEngine", "risk_engine" in b_content.lower()),
        ("PortfolioEngine", "portfolio_engine" in b_content.lower()),
        ("ExecutionEngine", "execution_engine" in b_content.lower()),
        ("BacktestEngine", "backtest_engine" in b_content.lower()),
        ("Telegram Menu", "telegram_menu" in b_content.lower() or "backtest_menu" in b_content.lower()),
        ("Vault", "vault" in b_content.lower()),
        ("Toobit WS", "toobit_ws" in b_content.lower() or "websocket" in b_content.lower()),
    ]
    for name, connected in checks:
        status = "✅ Connected" if connected else "❌ NOT connected"
        print(f"{status}: {name}")
else:
    print("❌ bootstrap.py not found")

# Check for TODOs, FIXMEs, NotImplemented
print("\n" + "="*80)
print("🚧 TODO / NotImplemented / Pass-only Check")
print("="*80)
todo_count = 0
for py_file in root.rglob("*.py"):
    try:
        content = py_file.read_text()
        if "TODO" in content or "FIXME" in content or "NotImplemented" in content or content.strip() == "" or content.count("pass") > 5:
            # Count
            todos = content.count("TODO") + content.count("FIXME")
            if todos > 0 or "NotImplemented" in content:
                print(f"{py_file.relative_to(root)}: TODO={todos}, NotImplemented={'NotImplemented' in content}")
                todo_count += 1
    except:
        pass

print(f"\nTotal files with TODO/NotImplemented: {todo_count}")

# Blueprint compliance
print("\n" + "="*80)
print("📋 BLUEPRINTS COMPLIANCE CHECK")
print("="*80)
checks = [
    ("10 Symbols", "TOP_10_SYMBOLS" in (bootstrap.read_text() if bootstrap.exists() else "")),
    ("14 Timeframes", "ALL_14_TFS" in (bootstrap.read_text() if bootstrap.exists() else "")),
    ("Crypto-Only No Forex", "Forex sessions REMOVED" in (bootstrap.read_text() if bootstrap.exists() else "") or "crypto-only" in (bootstrap.read_text() if bootstrap.exists() else "").lower()),
    ("Backtest Full History", (root / "backtest" / "backtest_engine.py").exists()),
    ("Telegram Backtest Menu", (root / "backtest" / "telegram_menu.py").exists()),
    ("13 Evidences", "evidence_engine" in (bootstrap.read_text() if bootstrap.exists() else "").lower()),
]

for name, ok in checks:
    print(f"{'✅' if ok else '❌'} {name}")

print("\n" + "="*80)
print("AUDIT COMPLETE - Run this script after each major update")
print("="*80)
