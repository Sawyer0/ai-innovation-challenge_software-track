from datetime import datetime
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


@app.get("/health")
def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status of database connectivity and AI API.
    """
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "unknown",
        "ai_api": "unknown"
    }
    
    # Check database
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Check AI API
    try:
        client = get_ai_client()
        # Just verify client is initialized
        status["ai_api"] = "available"
    except AIError as e:
        status["ai_api"] = f"error: {str(e)}"
        status["status"] = "degraded"
    except Exception as e:
        status["ai_api"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    return status


from .routers import courses, programs, sessions, upload, advisement

app.include_router(courses.router)
app.include_router(programs.router)
app.include_router(sessions.router)
app.include_router(upload.router)
app.include_router(advisement.router)
