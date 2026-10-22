from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai import analytics_ai_router, init_ai_db
from app.ai import router as ai_router
from app.analytics import init_analytics_db, monitoring_router
from app.analytics import router as analytics_router
from app.auth import init_db
from app.auth import router as auth_router
from app.campaigns import init_campaign_db, validation_router
from app.campaigns import router as campaigns_router
from app.core import configure_logging, get_logger, install_middleware, settings
from app.creatives import init_creative_db
from app.creatives import router as creatives_router
from app.publishing import activity_router, init_platform_db, init_publishing_db, platforms_router
from app.publishing import jobs_router as publishing_jobs_router
from app.publishing import router as publishing_router

# Configured at import time rather than inside the lifespan hook so the first
# records emitted during startup are already structured.
configure_logging(settings.log_level)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("startup", extra={"environment": settings.app_env, "ai_provider": settings.ai_provider})
    init_db()
    init_campaign_db()
    init_creative_db()
    init_ai_db()
    init_platform_db()
    init_publishing_db()
    init_analytics_db()
    yield
    logger.info("shutdown")


app = FastAPI(
    title="AdPilot API",
    version="0.1.0",
    description="Modular API for AI-assisted advertising workflows.",
    lifespan=lifespan,
)

install_middleware(app)

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
app.include_router(ai_router)
app.include_router(platforms_router)
app.include_router(validation_router)
app.include_router(publishing_router)
app.include_router(publishing_jobs_router)
app.include_router(activity_router)
app.include_router(analytics_router)
app.include_router(analytics_ai_router)
app.include_router(monitoring_router)


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
