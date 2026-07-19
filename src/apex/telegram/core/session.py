
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid

@dataclass
class NavigationStack:
    stack: List[str] = field(default_factory=list)
    
    def push(self, menu: str):
        self.stack.append(menu)
    
    def pop(self) -> Optional[str]:
        if len(self.stack) > 1:
            self.stack.pop()
            return self.stack[-1]
        return self.stack[0] if self.stack else "main"
    
    def peek(self) -> str:
        return self.stack[-1] if self.stack else "main"
    
    def clear(self):
        self.stack = ["main"]
    
    def breadcrumb(self) -> str:
        return " → ".join(self.stack)

@dataclass
class TelegramSession:
    user_id: int
    chat_id: int
    username: str = ""
    role: str = "viewer"  # owner, admin, analyst, viewer
    current_menu: str = "main"
    previous_menu: str = ""
    selected_symbol: str = "BTC"
    selected_timeframe: str = "1h"
    selected_optimizer: str = "signal"
    selected_strategy: str = ""
    selected_report: str = ""
    selected_trade: str = ""
    selected_position: str = ""
    language: str = "en"
    navigation_stack: NavigationStack = field(default_factory=NavigationStack)
    pagination_state: Dict[str, int] = field(default_factory=dict)
    temporary_data: Dict[str, Any] = field(default_factory=dict)
    pending_action: Optional[str] = None
    last_message_id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
    
    def __post_init__(self):
        if not self.navigation_stack.stack:
            self.navigation_stack.push("main")
    
    def touch(self):
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.expires_at = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
    
    def is_expired(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except:
            return False
    
    def set_menu(self, menu: str):
        self.previous_menu = self.current_menu
        self.current_menu = menu
        self.navigation_stack.push(menu)
        self.touch()
    
    def go_back(self) -> str:
        prev = self.navigation_stack.pop()
        self.current_menu = prev
        self.touch()
        return prev
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['navigation_stack'] = self.navigation_stack.stack
        return d

class SessionManager:
    """Session Manager per blueprint - Memory for now, Redis for enterprise"""
    def __init__(self):
        self.sessions: Dict[int, TelegramSession] = {}
        self._persistent_settings: Dict[int, Dict[str, Any]] = {}
    
    def get_or_create(self, user_id: int, chat_id: int, username: str = "", role: str = "viewer") -> TelegramSession:
        if user_id in self.sessions:
            session = self.sessions[user_id]
            if session.is_expired():
                # Keep persistent settings
                persistent = {
                    'language': session.language,
                    'role': session.role,
                }
                self._persistent_settings[user_id] = persistent
                session = self._create_new(user_id, chat_id, username, role)
            else:
                session.touch()
                return session
        # Check persistent
        if user_id in self._persistent_settings:
            pers = self._persistent_settings[user_id]
            role = pers.get('role', role)
        
        session = self._create_new(user_id, chat_id, username, role)
        self.sessions[user_id] = session
        return session
    
    def _create_new(self, user_id: int, chat_id: int, username: str, role: str) -> TelegramSession:
        # Restore persistent if exists
        persistent = self._persistent_settings.get(user_id, {})
        session = TelegramSession(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            role=persistent.get('role', role),
            language=persistent.get('language', 'en')
        )
        return session
    
    def get(self, user_id: int) -> Optional[TelegramSession]:
        return self.sessions.get(user_id)
    
    def update(self, session: TelegramSession):
        session.touch()
        self.sessions[session.user_id] = session
    
    def delete(self, user_id: int):
        if user_id in self.sessions:
            # Save persistent
            s = self.sessions[user_id]
            self._persistent_settings[user_id] = {
                'language': s.language,
                'role': s.role
            }
            del self.sessions[user_id]
    
    def cleanup_expired(self):
        expired = [uid for uid, s in self.sessions.items() if s.is_expired()]
        for uid in expired:
            self.delete(uid)
        return len(expired)
    
    def all_sessions(self) -> List[TelegramSession]:
        return list(self.sessions.values())
