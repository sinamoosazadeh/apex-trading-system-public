"""Rejection handler"""
class RejectionHandler:
    def handle(self, package, reason): return {"rejected": True, "reason": reason}
