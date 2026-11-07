import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router
from app.config import Settings
from app.db import Database
from app.events import EventBroker
from app.extractor import Extractor
from app.geo import Geocoder
from app.pipeline import Pipeline
from app.security import RateLimiter
from app.simulate import Simulator
from app.telegram import Telegram

ROOT = Path(__file__).resolve().parents[1]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {"level": record.levelname, "logger": record.name, "event": record.getMessage()}
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.getLogger("app").handlers = [handler]
        logging.getLogger("app").setLevel(settings.log_level)
        # HTTP client logs include request URLs, so keep them disabled to protect bot tokens.
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        db = Database(settings.db_path)
        await db.open()
        async with httpx.AsyncClient() as client:
            state = app.state
            state.settings, state.db = settings, db
            state.events = EventBroker()
            state.extractor = Extractor(settings, client)
            state.geo = Geocoder(db, settings, client)
            state.pipeline = Pipeline(db, settings, state.extractor, state.geo, state.events)
            state.telegram = Telegram(settings, db, client, state.pipeline, state.events)
            state.pipeline.telegram = state.telegram
            state.simulator = Simulator(state.pipeline)
            await state.pipeline.start()
            await state.telegram.start()
            try:
                yield
            finally:
                await state.simulator.pause()
                await state.telegram.stop()
                await state.pipeline.stop()
                await db.close()

    app = FastAPI(
        title="ReliefSync Desk",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    limiter = RateLimiter(240, 4)
    login_limiter = RateLimiter(5, 1 / 60)

    @app.middleware("http")
    async def security(request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        if request.url.path.startswith(("/api/", "/telegram/")) and not limiter.allow(ip):
            return JSONResponse(
                {"error": "rate_limit", "detail": "Please slow down"}, status_code=429
            )
        if request.url.path == "/api/login" and not login_limiter.allow(ip):
            return JSONResponse(
                {"error": "rate_limit", "detail": "Too many login attempts"}, status_code=429
            )
        if request.method in {"POST", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin not in {
                str(request.base_url).rstrip("/"),
                settings.public_base_url.rstrip("/"),
            }:
                return JSONResponse(
                    {"error": "forbidden", "detail": "Cross-origin write rejected"}, status_code=403
                )
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16384:
                    return JSONResponse(
                        {"error": "body_too_large", "detail": "Maximum request size is 16 KiB"},
                        status_code=413,
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers.update(
            {
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
                "X-Frame-Options": "DENY",
            }
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            {"error": str(exc.status_code), "detail": exc.detail}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "error": "validation",
                "detail": "Invalid request fields",
                "fields": [".".join(map(str, e["loc"])) for e in exc.errors()],
            },
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse({"error": "invalid_request", "detail": str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logging.getLogger("app").error("request_failed type=%s", type(exc).__name__)
        return JSONResponse(
            {"error": "internal", "detail": "An internal error occurred"}, status_code=500
        )

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/api/docs", include_in_schema=False)
    async def api_docs():
        return FileResponse(ROOT / "static/api-docs.html")

    @app.get("/")
    async def home():
        return FileResponse(ROOT / "static/index.html")

    @app.get("/{page}")
    async def page(page: str):
        if page not in {"about", "architecture", "eval", "join", "safety"}:
            raise HTTPException(404, "Page not found")
        return FileResponse(ROOT / "static" / f"{page}.html")

    return app


app = create_app()
