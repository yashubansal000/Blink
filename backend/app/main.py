from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.database import Base, engine
from app.routes import shorten, redirect

# Creates the short_links table if it doesn't already exist.
# Fine for now; once the schema stabilizes, switch to Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener", version="1.0.0")
logging.basicConfig(level=logging.INFO)

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
app.include_router(redirect.router, tags=["Redirect"])