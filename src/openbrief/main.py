from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from openbrief.api.briefs import router as briefs_router
from openbrief.api.dashboard import router as dashboard_router
from openbrief.api.health import router as health_router
from openbrief.api.projects import router as projects_router
from openbrief.api.setup import router as setup_router
from openbrief.api.source_items import router as source_items_router
from openbrief.api.webhooks import router as webhook_router
from openbrief.db import engine
from openbrief.security import require_api_key


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="OpenBrief API",
        version="0.1.0",
        description="Read-only project context collector and approval-based team brief API",
        lifespan=lifespan,
    )
    application.include_router(health_router)
    protected = [Depends(require_api_key)]
    application.include_router(projects_router, dependencies=protected)
    application.include_router(source_items_router, dependencies=protected)
    application.include_router(briefs_router, dependencies=protected)
    application.include_router(webhook_router, dependencies=protected)
    application.include_router(dashboard_router, dependencies=protected)
    application.include_router(setup_router, dependencies=protected)
    return application


app = create_app()
