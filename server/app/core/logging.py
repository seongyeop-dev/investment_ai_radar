from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_KEYS = ("api_key", "apikey", "authorization", "password", "secret", "token")
_INLINE_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b"
    r"(\s*[:=]\s*)(bearer\s+)?([^\s,;]+)"
)


def redact(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if any(part in normalized_key for part in _SENSITIVE_KEYS):
        return "***"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _INLINE_SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}***", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        context = getattr(record, "context", None)
        if isinstance(context, Mapping):
            payload["context"] = redact(context)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
