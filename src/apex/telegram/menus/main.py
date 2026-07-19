
from __future__ import annotations
from ..utils.keyboard_builder import KeyboardBuilder
from ..utils.message_builder import MessageBuilder

class MainMenu:
    @staticmethod
    def get_message(is_admin: bool = False, role: str = "viewer") -> str:
        return MessageBuilder.main_menu(is_admin=is_admin)
    
    @staticmethod
    def get_keyboard(is_admin: bool = False, is_owner: bool = False):
        return KeyboardBuilder.main_menu(is_admin=is_admin, is_owner=is_owner)
