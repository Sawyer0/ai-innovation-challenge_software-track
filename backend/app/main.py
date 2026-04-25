from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base, SessionLocal

# Import models so they are registered with SQLAlchemy
from . import models

# Create database tables
Base.metadata.create_all(bind=engine)

# Seed enrollment rules and financial aid constraints on startup
from .services.catalog_loader import seed_policy_data as _seed_policy_data
_db = SessionLocal()
try:
    _seed_policy_data(_db)
finally:
    _db.close()

app = FastAPI(title="BMCC AI-Powered Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to BMCC AI-Powered Backend"}

from .routers import courses, programs, sessions, transcript, advisement

app.include_router(courses.router)
app.include_router(programs.router)
app.include_router(sessions.router)
app.include_router(transcript.router)
app.include_router(advisement.router)
