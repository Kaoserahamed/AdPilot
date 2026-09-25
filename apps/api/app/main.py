from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(
    title="AdPilot API",
    version="0.1.0",
    description="Modular API for AI-assisted advertising workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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
