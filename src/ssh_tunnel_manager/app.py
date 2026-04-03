from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import build_router
from .runtime import TunnelRuntime
from .services import TunnelService


def create_app() -> FastAPI:
    app = FastAPI(title="SSH Tunnel Manager")
    runtime = TunnelRuntime()
    service = TunnelService(runtime)
    health_task: asyncio.Task[None] | None = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup() -> None:
        nonlocal health_task
        await service.startup()
        health_task = asyncio.create_task(service.health_loop())

    @app.on_event("shutdown")
    async def shutdown() -> None:
        nonlocal health_task
        if health_task:
            health_task.cancel()
            with suppress(asyncio.CancelledError):
                await health_task
            health_task = None
        await service.shutdown()

    app.include_router(build_router(service))
    return app


app = create_app()
