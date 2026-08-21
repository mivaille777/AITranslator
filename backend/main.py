from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.browser_context import router as browser_context_router
from backend.api.companion import router as companion_router
from backend.api.companion_stream import router as companion_stream_router
from backend.api.dependencies import (
    close_browser_context_service,
    close_companion_chat_service,
    close_quick_action_service,
    close_translation_service,
    get_browser_context_service,
)
from backend.api.health import router as health_router
from backend.api.overlay import router as overlay_router
from backend.api.quick_actions import router as quick_actions_router
from backend.api.research import router as research_router
from backend.api.translation import router as translation_router

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8766


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_browser_context_service().start()
    try:
        yield
    finally:
        close_browser_context_service()
        close_companion_chat_service()
        close_quick_action_service()
        close_translation_service()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AITranslator API",
        version="0.6.0",
        description="Local API boundary for the AITranslator WebReBuild desktop client.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(translation_router)
    app.include_router(browser_context_router)
    app.include_router(overlay_router)
    app.include_router(quick_actions_router)
    app.include_router(research_router)
    app.include_router(companion_router)
    app.include_router(companion_stream_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.getenv("AITRANS_API_HOST", DEFAULT_API_HOST)
    port = int(os.getenv("AITRANS_API_PORT", str(DEFAULT_API_PORT)))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
