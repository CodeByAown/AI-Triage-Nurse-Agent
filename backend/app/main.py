"""
Neural Hub AI Triage Nurse — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("neuralhub_starting", version=settings.app_version, env=settings.app_env)
    yield
    await engine.dispose()
    logger.info("neuralhub_shutdown")


app = FastAPI(
    title="Neural Hub AI Triage Nurse API",
    description=(
        "Production API for Neural Hub AI Triage Nurse — "
        "AI-powered patient triage and clinical decision support."
    ),
    version=settings.app_version,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Our team has been notified.",
            "type": "internal_error",
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "version": settings.app_version,
        "service": "Neural Hub AI Triage Nurse API",
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "service": "Neural Hub AI Triage Nurse API",
        "version": settings.app_version,
        "docs": "/docs",
    }
