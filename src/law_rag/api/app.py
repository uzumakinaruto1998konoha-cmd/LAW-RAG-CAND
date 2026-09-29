"""FastAPI application factory for the LAW-RAG REST API (docs/11).

Conventions implemented here:
- Every route lives under the ``/api/v1`` prefix and is described in OpenAPI.
- Authentication and authorization are always enforced on the server.
- Failures return the standard error envelope with a stable code, a safe
  message, the request id, and optional field errors.
"""

from __future__ import annotations

import logging
from pathlib import Path
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from law_rag.ingestion.authorization import AuthorizationError
from law_rag.ingestion.errors import IngestionError

from .container import ApiContainer
from .errors import ApiError, FieldError, ValidationApiError, classify_error, error_body
from .routers import chat, documents, health, identity, ingestion, search

LOGGER = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

DESCRIPTION = (
    "Tra cứu văn bản pháp luật và hỏi đáp có dẫn chiếu. Mọi nội dung trả về đã được "
    "kiểm tra ACL phía server; tài liệu ngoài quyền được báo 404 để không lộ sự tồn tại."
)


def create_app(container: ApiContainer | None = None) -> FastAPI:
    """Build the ASGI application with all ``/api/v1`` routers attached."""
    app = FastAPI(
        title="LAW-RAG-CAND API",
        version="1.0",
        description=DESCRIPTION,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.container = container if container is not None else ApiContainer()

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    def _respond(request: Request, error: ApiError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        return JSONResponse(status_code=error.status_code, content=error_body(error, request_id))

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _respond(request, exc)

    @app.exception_handler(AuthorizationError)
    async def handle_authorization_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        mapped = classify_error(exc) or ApiError("Bị từ chối truy cập.")
        return _respond(request, mapped)

    @app.exception_handler(IngestionError)
    async def handle_ingestion_error(request: Request, exc: IngestionError) -> JSONResponse:
        mapped = classify_error(exc) or ApiError("Yêu cầu ingestion không xử lý được.")
        return _respond(request, mapped)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = tuple(
            FieldError(
                field=".".join(str(part) for part in error.get("loc", ()) if part != "body") or "body",
                message=str(error.get("msg", "Giá trị không hợp lệ.")),
            )
            for error in exc.errors()
        )
        return _respond(
            request, ValidationApiError("Dữ liệu yêu cầu không hợp lệ.", field_errors=field_errors)
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        # Log only the error type: exception text may carry sensitive data (docs/11 §1).
        LOGGER.error(
            "Unhandled API error request_id=%s path=%s error_type=%s",
            request_id,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=error_body(ApiError("Lỗi hệ thống, vui lòng thử lại sau."), request_id),
        )

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(identity.router, prefix=API_PREFIX)
    app.include_router(search.router, prefix=API_PREFIX)
    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(documents.router, prefix=API_PREFIX)
    app.include_router(ingestion.router, prefix=API_PREFIX)

    dist_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if dist_dir.is_dir():
        from fastapi.responses import FileResponse
        from starlette.staticfiles import StaticFiles

        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(request: Request, full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content=error_body(
                        ApiError("Endpoint API không tồn tại."),
                        getattr(request.state, "request_id", "-"),
                    ),
                )
            file_path = dist_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(dist_dir / "index.html")

    return app

