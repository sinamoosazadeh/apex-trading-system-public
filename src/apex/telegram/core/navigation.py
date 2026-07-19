
from __future__ import annotations
from typing import List, Dict, Any, Optional

class NavigationManager:
    """Navigation Stack Manager per blueprint"""
    def __init__(self):
        self.global_breadcrumb: Dict[int, List[str]] = {}
    
    def get_breadcrumb(self, user_id: int, stack: List[str]) -> str:
        if not stack:
            return "🏠 Main"
        breadcrumb = "🏠 " + " → ".join(stack[:1])
        for item in stack[1:]:
            breadcrumb += f"\n└── {item}"
        return breadcrumb
    
    def format_breadcrumb(self, stack: List[str]) -> str:
        if not stack:
            return "🏠 Main Menu"
        # Format as per blueprint: 🏠 Main └── 📊 Backtest └── BTCUSDT └── 1H
        if len(stack) == 1:
            return f"🏠 {stack[0]}"
        result = f"🏠 {stack[0]}"
        for i, item in enumerate(stack[1:], 1):
            indent = "      " * (i-1)
            result += f"\n{indent}└── {item}"
        return result
    
    def get_back_target(self, current_stack: List[str]) -> str:
        if len(current_stack) <= 1:
            return "main"
        return current_stack[-2] if len(current_stack) >= 2 else "main"
