
from ..utils.keyboard_builder import KeyboardBuilder

class PortfolioMenu:
    @staticmethod
    def main_menu():
        return {
            "message": "💼 **Portfolio**\n\nSelect view:",
            "keyboard": KeyboardBuilder.build([
                [{"text": "📊 Summary", "callback": "portfolio.summary"}, {"text": "📈 Positions", "callback": "portfolio.positions"}],
                [{"text": "📋 Closed Trades", "callback": "portfolio.closed"}, {"text": "📈 Performance", "callback": "portfolio.performance"}],
                [{"text": "📤 Export", "callback": "portfolio.export"}],
            ], current_menu="portfolio")
        }
