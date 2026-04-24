from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base

# Import models so they are registered with SQLAlchemy
from . import models

# Create database tables
Base.metadata.create_all(bind=engine)

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
