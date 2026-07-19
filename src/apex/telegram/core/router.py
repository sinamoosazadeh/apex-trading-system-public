
from __future__ import annotations
from typing import Dict, Callable, Any, Optional
import re
import logging

log = logging.getLogger(__name__)

class CallbackRouter:
    """Callback Router per blueprint - module.action.target format"""
    def __init__(self):
        self.routes: Dict[str, Callable] = {}
        self.pattern_routes: List[tuple] = []  # (pattern, handler)
    
    def register(self, pattern: str, handler: Callable):
        """Register callback pattern, e.g. 'backtest.symbol.BTC' or 'backtest.symbol.*'"""
        if "*" in pattern or ":" in pattern:
            # Convert to regex
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*").replace(":", r"(?P<\w+>.*)")
            # Actually simpler: use fnmatch style
            self.pattern_routes.append((pattern, handler))
        else:
            self.routes[pattern] = handler
    
    def route(self, callback_data: str) -> Optional[tuple]:
        """Route callback_data to handler, returns (handler, params)"""
        # Exact match
        if callback_data in self.routes:
            return self.routes[callback_data], {}
        
        # Pattern match - module.action.target
        parts = callback_data.split(".")
        if len(parts) >= 2:
            # Try wildcard matches
            for pattern, handler in self.pattern_routes:
                if self._match_pattern(pattern, callback_data):
                    params = self._extract_params(pattern, callback_data)
                    return handler, params
        
        # Try prefix match
        for route_pattern, handler in self.routes.items():
            if callback_data.startswith(route_pattern):
                return handler, {"raw": callback_data}
        
        log.warning(f"No route found for callback: {callback_data}")
        return None
    
    def _match_pattern(self, pattern: str, data: str) -> bool:
        # Simple wildcard matching
        # pattern: backtest.symbol.* should match backtest.symbol.BTC
        if pattern.endswith(".*"):
            return data.startswith(pattern[:-2])
        if "*" in pattern:
            # Convert to regex
            regex = pattern.replace(".", r"\.").replace("*", ".*")
            return bool(re.match(f"^{regex}$", data))
        return pattern == data
    
    def _extract_params(self, pattern: str, data: str) -> Dict[str, str]:
        params = {}
        # If pattern has *, extract last part
        if ".*" in pattern:
            prefix = pattern[:-2]
            if data.startswith(prefix):
                params['value'] = data[len(prefix):].lstrip(".")
        # Extract by position
        pattern_parts = pattern.split(".")
        data_parts = data.split(".")
        for i, p_part in enumerate(pattern_parts):
            if p_part == "*" and i < len(data_parts):
                params[f"param_{i}"] = data_parts[i]
        params['raw'] = data
        return params

class MessageRouter:
    """Routes text messages / commands"""
    def __init__(self):
        self.command_routes: Dict[str, Callable] = {}
    
    def register_command(self, command: str, handler: Callable):
        self.command_routes[command.lower().lstrip("/")] = handler
    
    def route_command(self, text: str) -> Optional[tuple]:
        if not text.startswith("/"):
            return None
        cmd = text.split()[0].lstrip("/").lower().split("@")[0]
        args = text.split()[1:]
        if cmd in self.command_routes:
            return self.command_routes[cmd], {"args": args, "raw": text}
        return None
