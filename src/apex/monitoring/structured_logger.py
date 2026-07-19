"""Structured JSON Logger for enterprise-grade observability."""
from __future__ import annotations

import json
import sys
import time
from typing import Any
import logging

from .contracts import LogEntry

class StructuredLogger:
    """Outputs logs as structured JSON to stdout/stderr."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self._logger = logging.getLogger(module_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # جلوگیری از چاپ تکراری لاگ‌ها
        
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)

    def log(self, level: str, message: str, trace_id: str = "", **metadata: Any) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            level=level.upper(),
            module=self.module_name,
            message=message,
            trace_id=trace_id,
            metadata=metadata
        )
        
        log_dict = {
            "timestamp": entry.timestamp,
            "level": entry.level,
            "module": entry.module,
            "message": entry.message,
            "trace_id": entry.trace_id,
            **entry.metadata
        }
        
        log_str = json.dumps(log_dict, default=str)
        
        if entry.level in ["ERROR", "CRITICAL"]:
            self._logger.error(log_str)
        elif entry.level == "WARNING":
            self._logger.warning(log_str)
        else:
            self._logger.info(log_str)

    def info(self, message: str, **metadata: Any) -> None:
        self.log("INFO", message, **metadata)

    def warning(self, message: str, **metadata: Any) -> None:
        self.log("WARNING", message, **metadata)

    def error(self, message: str, **metadata: Any) -> None:
        self.log("ERROR", message, **metadata)
