from fastapi import FastAPI

from app.database import Base, engine
from app.routes import shorten, redirect

# Creates the short_links table if it doesn't already exist.
# Fine for now; once the schema stabilizes, switch to Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener", version="1.0.0")

app.include_router(shorten.router, prefix="/api", tags=["Shorten"])
app.include_router(redirect.router, tags=["Redirect"])