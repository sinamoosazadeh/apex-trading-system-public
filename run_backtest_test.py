import asyncio
import logging
from apex.infrastructure.exchanges.toobit_client import ToobitClient
from apex.engines.kernel import CentralDecisionKernel
from apex.engines.probability_engine import ProbabilityEngine
from apex.engines.governance import GovernanceEngine, GovernancePolicy
from apex.engines.decision_engine import DecisionEngine
from apex.engines.risk_engine import RiskEngine
from apex.engines.portfolio_engine import PortfolioEngine
from apex.engines.execution_engine import ExecutionEngine
from apex.engines.digital_twin import DigitalTwin
from apex.engines.meta_intelligence import MetaIntelligenceEngine
from apex.features.feature_store import FeatureStore
from apex.research.knowledge_base import KnowledgeBase
from apex.research.research_engine import ResearchEngine
from apex.monitoring.health_monitor import HealthMonitor
from apex.domain.market import MarketBar
from apex.domain.trading import Position

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("TestRunner")

class MockApp:
    def __init__(self):
        self.mode = "PAPER"
    async def send_telegram_signal(self, msg):
        print(f"\n[TELEGRAM SIGNAL MOCK]\n{msg}\n")

async def main():
    log.info("Initializing components for Backtest Test...")
    client = ToobitClient(api_key="test", api_secret="test")
    
    feature_store = FeatureStore()
    prob_engine = ProbabilityEngine()
    knowledge_base = KnowledgeBase()
    research_engine = ResearchEngine(knowledge_base, prob_engine)
    portfolio_engine = PortfolioEngine(initial_capital=10000.0)
    governance = GovernanceEngine(GovernancePolicy())
    decision_engine = DecisionEngine(governance)
    risk_engine = RiskEngine()
    
    class MockExec:
        async def execute_blueprint(self, bp): return {"orderId": "mock_bt_123", "status": "NEW"}
        
    execution_engine = MockExec()
    digital_twin = DigitalTwin(10000.0)
    health_monitor = HealthMonitor()
    meta_engine = MetaIntelligenceEngine(health_monitor)
    
    kernel = CentralDecisionKernel(
        feature_store, prob_engine, decision_engine, risk_engine, portfolio_engine,
        execution_engine, research_engine, digital_twin, meta_engine, health_monitor
    )
    kernel.app = MockApp()
    
    log.info("Fetching 100 5m ETH candles from Toobit...")
    raw_klines = await client.get_klines("SOL-SWAP-USDT", "15m", 200)
    
    bars = []
    for k in raw_klines:
        bar = MarketBar(
            timestamp=k[0], open=float(k[1]), high=float(k[2]),
            low=float(k[3]), close=float(k[4]), volume=float(k[5]),
            symbol="SOL-SWAP-USDT", exchange="toobit", timeframe="5m"
        )
        bars.append(bar)
        
    log.info(f"Fetched {len(bars)} bars. Running CDK pipeline sequentially...")
    
    for i, bar in enumerate(bars):
        await kernel.process_bar(bar)
        
        for pos in list(kernel.portfolio_engine.open_positions.values()):
            if pos.symbol == bar.symbol and pos.status == "OPEN":
                hit_sl = (pos.direction == "LONG" and bar.low <= pos.stop_loss) or \
                         (pos.direction == "SHORT" and bar.high >= pos.stop_loss)
                hit_tp = (pos.direction == "LONG" and bar.high >= pos.take_profit) or \
                         (pos.direction == "SHORT" and bar.low <= pos.take_profit)
                if hit_sl or hit_tp:
                    exit_price = pos.stop_loss if hit_sl else pos.take_profit
                    await kernel.close_position_workflow(pos, exit_price, "Backtest SL/TP Hit")
                    
    log.info("Backtest finished.")
    state = kernel.portfolio_engine.get_state()
    total_trades = len(kernel.portfolio_engine.closed_trades)
    wins = len([t for t in kernel.portfolio_engine.closed_trades if t.win])
    
    print("\n" + "="*40)
    print("📊 BACKTEST RESULTS (SOL-SWAP-USDT 5m)")
    print(f"Total Bars Processed: {len(bars)}")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins}")
    print(f"Final Equity: {state.total_equity:.2f} USDT")
    print(f"Net PnL: {kernel.portfolio_engine.realized_pnl:.2f} USDT")
    print("="*40 + "\n")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
