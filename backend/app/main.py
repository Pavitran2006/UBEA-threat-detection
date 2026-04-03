from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import FRONTEND_DIR, STATIC_DIR
from .database import Base, engine, ensure_user_columns, ensure_login_logs_columns
from .routes.auth_routes import router as auth_router
from .routes.dashboard_routes import router as dashboard_router
from .routes.admin_routes import router as admin_router
from .websocket_logs import events_websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
ensure_user_columns(engine)
ensure_login_logs_columns(engine)

app = FastAPI(title="UEBA - User and Entity Behaviour Analytics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.add_api_websocket_route("/ws/events", events_websocket)


@app.get("/", response_class=FileResponse)
async def serve_home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login", response_class=FileResponse)
async def serve_login():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/signup", response_class=FileResponse)
async def serve_signup():
    return FileResponse(FRONTEND_DIR / "signup.html")


@app.get("/dashboard", response_class=FileResponse)
async def serve_dashboard():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/features", response_class=FileResponse)
async def serve_features():
    return FileResponse(FRONTEND_DIR / "features.html")


@app.get("/forgot-password", response_class=FileResponse)
async def serve_forgot_password():
    return FileResponse(FRONTEND_DIR / "forgot-password.html")


@app.get("/verify-otp", response_class=FileResponse)
async def serve_verify_otp():
    return FileResponse(FRONTEND_DIR / "verify-otp.html")


@app.get("/reset-password", response_class=FileResponse)
async def serve_reset_password():
    return FileResponse(FRONTEND_DIR / "reset-password.html")


@app.on_event("startup")
async def startup_event():
    logger.info("UEBA Server Started")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
