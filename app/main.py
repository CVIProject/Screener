import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.regime import router as regime_router
from app.api.routes.screener import router as screener_router
from app.core.config import settings
from app.core.exception_handlers import (
    register_exception_handlers,
)
from app.core.logging_config import configure_logging


configure_logging()

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "ALLOWED_ORIGINS", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-Request-ID",
        "X-Process-Time",
    ],
)


@app.middleware("http")
async def add_request_information(
    request: Request,
    call_next,
):
    request_id = (
        request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )

    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = (
        f"{process_time:.3f}"
    )

    return response


register_exception_handlers(app)

app.include_router(screener_router)
app.include_router(regime_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.APP_TITLE,
        "status": "running",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.APP_TITLE,
    }