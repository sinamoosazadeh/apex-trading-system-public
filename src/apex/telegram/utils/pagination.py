
from __future__ import annotations
from typing import List, Dict, Any

class PaginationManager:
    def __init__(self, items: List[Any], page_size: int = 5):
        self.items = items
        self.page_size = page_size
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)
    
    def get_page(self, page: int) -> List[Any]:
        if page < 1:
            page = 1
        if page > self.total_pages:
            page = self.total_pages
        start = (page - 1) * self.page_size
        end = start + self.page_size
        return self.items[start:end]
    
    def get_page_info(self, page: int) -> Dict[str, Any]:
        return {
            "current": page,
            "total": self.total_pages,
            "has_prev": page > 1,
            "has_next": page < self.total_pages,
            "total_items": len(self.items)
        }
