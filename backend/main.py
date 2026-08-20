from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.health import router as health_router

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8766


def create_app() -> FastAPI:
    app = FastAPI(
        title="AITranslator API",
        version="0.1.0",
        description="Local API boundary for the AITranslator WebReBuild desktop client.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.getenv("AITRANS_API_HOST", DEFAULT_API_HOST)
    port = int(os.getenv("AITRANS_API_PORT", str(DEFAULT_API_PORT)))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
