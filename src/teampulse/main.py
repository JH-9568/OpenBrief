from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from teampulse.api.briefs import router as briefs_router
from teampulse.api.health import router as health_router
from teampulse.api.projects import router as projects_router
from teampulse.api.source_items import router as source_items_router
from teampulse.api.webhooks import router as webhook_router
from teampulse.db import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="TeamPulse API",
        version="0.1.0",
        description="Read-only project context collector and approval-based team brief API",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    application.include_router(projects_router)
    application.include_router(source_items_router)
    application.include_router(briefs_router)
    application.include_router(webhook_router)
    return application


app = create_app()
