"""Barebones FastAPI RAG service: ingest + query."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import router
from app.core.config import settings
from app.core.db import close_db, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Open Postgres and apply schema on startup."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Classic RAG over logistics knowledge documents with tenant-scoped hybrid search.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
