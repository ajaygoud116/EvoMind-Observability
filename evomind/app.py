from __future__ import annotations

import logging

import fastapi
from fastapi import FastAPI

from evomind.api.routes import router
from evomind.config.settings import Settings
from evomind.orchestration.lifecycle import LifecycleManager
from evomind.orchestration.orchestrator import Orchestrator

logger = logging.getLogger("evomind")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    lifecycle = LifecycleManager(settings)
    registry = lifecycle.startup()

    orchestrator = Orchestrator(registry)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
    )

    app.state.settings = settings
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.lifecycle = lifecycle

    app.include_router(router)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        lifecycle.shutdown()

    return app
