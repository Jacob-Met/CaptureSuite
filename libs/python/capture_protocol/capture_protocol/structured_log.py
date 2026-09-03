# SPDX-License-Identifier: Apache-2.0
"""Structured JSON Lines logging matching docs/design/OPERATIONS.md."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_LEVEL_NAME = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warn",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


def _qpc_ns() -> int:
    return time.perf_counter_ns()


def _ts_utc() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def default_log_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "CaptureSuite" / "logs"
    return Path.home() / ".capturesuite" / "logs"


class JsonLineFormatter(logging.Formatter):
    def __init__(self, component: str) -> None:
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts_utc": _ts_utc(),
            "qpc_ns": _qpc_ns(),
            "level": _LEVEL_NAME.get(record.levelno, "info"),
            "component": getattr(record, "component", self.component),
            "pid": os.getpid(),
            "event": getattr(record, "event", "message"),
            "msg": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "source_id": getattr(record, "source_id", None),
            "stream_id": getattr(record, "stream_id", None),
            "seq": getattr(record, "seq", None),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class StructuredLogger:
    def __init__(self, component: str = "desktop") -> None:
        self.component = component
        self.session_id: str | None = None
        self._logger = logging.getLogger(f"capture.{component}")
        self._logger.handlers.clear()
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)

    def configure(
        self,
        *,
        log_dir: Path | None = None,
        level: int = logging.INFO,
        also_stderr: bool = True,
    ) -> None:
        directory = log_dir or default_log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        self._logger.handlers.clear()
        self._logger.setLevel(level)
        formatter = JsonLineFormatter(self.component)
        fh = RotatingFileHandler(
            directory / f"{self.component}.log",
            maxBytes=64 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)
        if also_stderr:
            sh = logging.StreamHandler()
            sh.setLevel(logging.WARNING)
            sh.setFormatter(formatter)
            self._logger.addHandler(sh)

    def set_session_id(self, session_id: str | None) -> None:
        self.session_id = session_id

    def _emit(
        self,
        level: int,
        event: str,
        msg: str,
        *,
        source_id: str | None = None,
        stream_id: str | None = None,
        seq: int | None = None,
        **fields: Any,
    ) -> None:
        if not self._logger.handlers:
            self.configure()
        self._logger.log(
            level,
            msg,
            extra={
                "component": self.component,
                "event": event,
                "session_id": self.session_id,
                "source_id": source_id,
                "stream_id": stream_id,
                "seq": seq,
                "fields": fields,
            },
        )

    def info(self, event: str, msg: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, msg, **fields)

    def warn(self, event: str, msg: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, msg, **fields)

    def error(self, event: str, msg: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, msg, **fields)

    def critical(self, event: str, msg: str, **fields: Any) -> None:
        self._emit(logging.CRITICAL, event, msg, **fields)


_default: StructuredLogger | None = None


def get_logger(component: str = "desktop") -> StructuredLogger:
    global _default
    if _default is None or _default.component != component:
        _default = StructuredLogger(component)
        _default.configure()
    return _default
