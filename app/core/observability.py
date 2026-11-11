# app/core/observability.py
"""
Logging and request tracing for production.

LOG_FORMAT=json   one JSON object per log line (for log search and alerting)
LOG_LEVEL=INFO    root log level

Every request gets an id (the caller's X-Request-ID when given, otherwise a new one). The id is
returned in the X-Request-ID header and added to every log line written while serving it.
"""

import contextvars
import json
import logging
import os
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

QUIET_PATHS = ("/api/health", "/api/ready")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            data.update(extra)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root.handlers = [handler]


class RequestContextMiddleware:
    """Pure ASGI middleware: request id, response header and one access-log line per request."""

    def __init__(self, app):
        self.app = app
        self.log = logging.getLogger("app.access")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")[:64]
        rid = incoming if incoming.replace("-", "").isalnum() and incoming else uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            if not path.endswith(QUIET_PATHS):
                self.log.info(
                    "%s %s -> %s",
                    scope.get("method"), path, status["code"],
                    extra={"fields": {
                        "method": scope.get("method"), "path": path, "status": status["code"],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }},
                )
            request_id_var.reset(token)
