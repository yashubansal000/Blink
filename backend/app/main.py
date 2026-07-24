from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging, asyncio

from app.database import Base, engine
from app.routes import shorten, redirect, report
from app.models import short_link, link_report, click_event
from app.workers.analytics import run_analytics_worker

# Creates the short_links table if it doesn't already exist.
# Fine for now; once the schema stabilizes, switch to Alembic migrations.
Base.metadata.create_all(bind=engine)


logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def start_background_workers(app: FastAPI):
    worker = asyncio.create_task(run_analytics_worker())

    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="URL Shortener",
    version="1.0.0",
    lifespan=start_background_workers,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://blink-ivory-sigma.vercel.app",
        ], # needs to tighten to your actual frontend URL once deployed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(shorten.router, prefix="/api", tags=["Shorten"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(redirect.router, tags=["Redirect"])