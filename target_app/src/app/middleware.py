import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app import config
from app.logging_setup import request_id_var

access_log = logging.getLogger("app.access")
error_log = logging.getLogger("app.errors")


async def request_logging(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    fields = {"method": request.method, "path": request.url.path}
    try:
        try:
            response = await call_next(request)
        except Exception:
            error_log.exception("unhandled exception", extra=fields)
            response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        fields |= {"status": response.status_code, "latency_ms": latency_ms}
        access_log.info("request", extra=fields)
        if latency_ms > config.SLOW_REQUEST_MS:
            access_log.warning("slow request", extra=fields)
        response.headers["x-request-id"] = request_id
        return response
    finally:
        request_id_var.reset(token)
