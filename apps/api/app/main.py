from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import init_db, router as auth_router
from .campaigns import init_campaign_db, router as campaigns_router
from .creatives import init_creative_db, router as creatives_router
from .config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_campaign_db()
    init_creative_db()
    yield


app = FastAPI(
    title="AdPilot API",
    version="0.1.0",
    description="Modular API for AI-assisted advertising workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(campaigns_router)
app.include_router(creatives_router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "adpilot-api", "version": app.version}


@app.get("/api/ready", tags=["system"])
def ready() -> dict[str, str | bool]:
    return {
        "status": "ready",
        "environment": settings.app_env,
        "integrations": "live" if settings.live_external_apis else "sandbox",
        "ai_provider": settings.ai_provider,
    }
