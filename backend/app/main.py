import app.compat  # noqa: F401
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import VaultException
from app.core.logging import logger
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Vault backend services...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Database table check deferred: {e}")
    yield
    logger.info("Shutting down Vault backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000

    # Security Headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Log request lifecycle (redacted)
    if not request.url.path.endswith("/health"):
        logger.info(
            "HTTP request processed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(process_time, 2),
            },
        )

    return response


@app.exception_handler(VaultException)
async def vault_exception_handler(request: Request, exc: VaultException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled server error: {str(exc)}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method},
    )
    # Mask internal stack traces in response to prevent information disclosure
    detail = "Internal server error" if settings.ENVIRONMENT == "production" else str(exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


# Mount routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve frontend HTML directly from root
from fastapi.responses import FileResponse
import os

@app.get("/", include_in_schema=False)
async def serve_index():
    for candidate in ["/app/index.html", "index.html", os.path.join(os.path.dirname(__file__), "..", "..", "index.html")]:
        if os.path.exists(candidate):
            return FileResponse(candidate)
    return JSONResponse(status_code=404, content={"detail": "index.html not found"})

@app.get("/preview.html", include_in_schema=False)
async def serve_preview():
    for candidate in ["/app/preview.html", "preview.html", os.path.join(os.path.dirname(__file__), "..", "..", "preview.html")]:
        if os.path.exists(candidate):
            return FileResponse(candidate)
    return JSONResponse(status_code=404, content={"detail": "preview.html not found"})

# Direct root health endpoint for standard load balancers & Docker healthchecks
@app.get("/health", tags=["Health"])
def root_health():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/readiness", tags=["Health"])
def root_readiness(request: Request):
    from app.api.v1.health import readiness_check
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        return readiness_check(db=db)
    finally:
        db.close()
