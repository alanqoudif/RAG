import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.config import get_settings
from app.exceptions import AppError, error_body
from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", environment=get_settings().environment)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Multi-Tenant Text-to-SQL and Document Chat Platform",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_request_error", path=request.url.path)
            body = error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id)
            response = JSONResponse(status_code=500, content=body)
        response.headers["X-Request-ID"] = request_id
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        route_path = route.path if route is not None else request.url.path
        REQUEST_COUNT.labels(request.method, route_path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, route_path).observe(elapsed)
        logger.info(
            "request_completed",
            method=request.method,
            path=route_path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", None)
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, request_id),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("HTTP_ERROR", str(exc.detail), request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Invalid request payload.", request_id),
        )

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
