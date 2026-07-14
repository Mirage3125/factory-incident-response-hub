import logging
import re
from typing import Any


SENSITIVE_PATTERNS = (
    re.compile(r"(token=)([^\s]+)", re.IGNORECASE),
    re.compile(r"(password=)([^\s]+)", re.IGNORECASE),
    re.compile(r"(resume_url=)([^\s]+)", re.IGNORECASE),
)


def mask_sensitive_value(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:2]}{'*' * (len(value) - 2)}"
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def mask_message(message: str) -> str:
    masked = message
    for pattern in SENSITIVE_PATTERNS:
        masked = pattern.sub(lambda match: f"{match.group(1)}{mask_sensitive_value(match.group(2))}", masked)
    return masked


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        record.msg = mask_message(rendered)
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
