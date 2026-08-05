from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes.regime import (
    router as regime_router,
)
from app.api.routes.screener import (
    router as screener_router,
)
from app.api.routes.consensus import (
    router as consensus_router,
)


app = FastAPI(
    title=(
        "CVI Stock Screener and "
        "Market Regime Service"
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-New-Observation-Date",
        "X-New-BAML-Value",
        "X-New-Quad",
        "X-New-Confirmed-Regime",
    ],
)

app.include_router(
    screener_router
)

app.include_router(
    regime_router
)

app.include_router(
    consensus_router
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Application running successfully",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }