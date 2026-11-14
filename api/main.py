"""FastAPI 앱 진입점: uvicorn api.main:app --workers 1"""
import logging
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import init_db
from .errors import ApiError, error_response
from .routes import router

logger = logging.getLogger("api")

MAX_BODY_BYTES = 3_145_728
CSP = "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


def create_app() -> FastAPI:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    register_handlers(application)
    application.middleware("http")(common_middleware)
    application.include_router(router)  # /api 먼저, 정적 파일은 그 뒤에 마운트
    application.mount("/", StaticFiles(directory=WEB_DIR, html=True, check_dir=False), name="web")
    return application


def add_security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = CSP
    return response


async def common_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """본문 크기 검사, 예기치 못한 오류의 500 변환, 보안 헤더 부착."""
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY_BYTES:
        response: Response = error_response(413, "REQUEST_TOO_LARGE", "요청 본문은 3MB 이하여야 합니다.")
    else:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("처리되지 않은 오류")
            response = error_response(500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")
    return add_security_headers(response)


def register_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def on_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.headers)

    @application.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        parts = [f"{err['loc'][-1] if err['loc'] else 'request'}: {err['msg']}" for err in exc.errors()]
        return error_response(422, "VALIDATION_ERROR", "; ".join(parts) or "잘못된 요청입니다.")

    @application.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "BAD_REQUEST")
        message = "요청을 처리할 수 없습니다." if exc.status_code >= 500 else str(exc.detail)
        return error_response(exc.status_code, code, message, getattr(exc, "headers", None))


app = create_app()
