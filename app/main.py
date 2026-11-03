import os
import logging
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()

# Setup structured logging
log_handlers = [logging.StreamHandler()]
try:
    log_handlers.append(logging.FileHandler("ueba_security.log", encoding="utf-8"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("ueba")
logger.info("UEBA Security System Starting up...")

from app.database import Base, engine, check_db_connection
from app.routes import router
from app.services.simulation_service import simulator

app = FastAPI(
    title="UEBA Threat Detection Platform",
    description="User and Entity Behavior Analytics for Insider Threat Detection",
    version="1.0.0"
)

# CORS Configuration
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware
session_secret = os.getenv("SECRET_KEY")
if not session_secret:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("CRITICAL: SECRET_KEY environment variable is required in production.")
    session_secret = "dev-insecure-secret-key-change-in-production"

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret
)

# Mount static files with absolute path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
uploads_dir = os.path.join(STATIC_DIR, "uploads", "profile_pics")
os.makedirs(uploads_dir, exist_ok=True)

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    logger.warning(f"Static directory not found at: {STATIC_DIR}")

# Include application routes
app.include_router(router)

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint for deployment monitoring and load balancers."""
    db_ok, db_msg = check_db_connection()
    status_str = "healthy" if db_ok else "degraded"
    return {
        "status": status_str,
        "service": "UEBA Threat Detection Platform",
        "database": {
            "connected": db_ok,
            "message": db_msg
        },
        "simulator_active": getattr(simulator, "running", False),
        "version": "1.0.0"
    }

@app.on_event("startup")
async def startup_event():
    # Safely ensure database tables are initialized
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Error during database table creation on startup: {e}")

    # Simulator is disabled by default in production; enabled via ENABLE_SIMULATION=true
    enable_simulation = os.getenv("ENABLE_SIMULATION", "false").lower() in ("true", "1", "yes")
    if enable_simulation:
        logger.info("ENABLE_SIMULATION is true: starting background telemetry simulator.")
        asyncio.create_task(simulator.start())
    else:
        logger.info("ENABLE_SIMULATION is false/unset: background simulator remains disabled.")
