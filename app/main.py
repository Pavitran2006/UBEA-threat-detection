import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import Base, engine
from app.routes import router
from app.services.simulation_service import simulator
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ueba_security.log")
    ]
)
logger = logging.getLogger("ueba")
logger.info("UEBA Security System Starting up...")

app = FastAPI(title="UEBA Security System")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "fallback-dev-secret-change-in-production")
)

# Mount static files so url_for('static', path='...') works in templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")

Base.metadata.create_all(bind=engine)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    # Start the simulation service in the background
    asyncio.create_task(simulator.start())
