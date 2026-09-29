from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (register tables)
from app.config import get_settings
from app.db import Base, engine
from app.routers import alerts, auth, billing, devices, ingest, readings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fine for a sample project; use Alembic migrations in production.
    Base.metadata.create_all(engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (auth, billing, devices, ingest, readings, alerts):
        app.include_router(r.router, prefix="/api/v1")

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok", "billing": "stripe" if settings.stripe_enabled else "mock"}

    return app


app = create_app()
