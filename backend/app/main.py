import sys
import os

# Add backend directory to sys.path to resolve 'app' imports seamlessly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.connection import init_db
from app.api.routes import commands, shopping, products, suggestions, auth
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs"
)

# Configure CORS origins cleanly
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if settings.FRONTEND_URL:
    frontend_origin = settings.FRONTEND_URL.strip().rstrip("/")
    if frontend_origin == "*":
        allowed_origins = ["*"]
    elif frontend_origin not in allowed_origins:
        allowed_origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(commands.router, prefix=settings.API_PREFIX)
app.include_router(shopping.router, prefix=settings.API_PREFIX)
app.include_router(products.router, prefix=settings.API_PREFIX)
app.include_router(suggestions.router, prefix=settings.API_PREFIX)

@app.on_event("startup")
def startup_event():
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Voice Shopping Assistant API started successfully.")

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": f"{settings.API_PREFIX}/docs"
    }

@app.get("/health")
def health_check():
    from app.database.connection import get_db_status
    db_stat = get_db_status()
    return {
        "status": db_stat["status"],
        "database": db_stat["database"]
    }

