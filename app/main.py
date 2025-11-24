"""
FastAPI Application Entry Point

This module initializes the FastAPI application and integrates:
- Telegram bot webhook
- Database connections
- API routes
- Lifecycle events
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import check_database_connection, close_database_connection
from app.bot import webhook_router, startup_webhook, shutdown_webhook

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 60)
logger.info("Telegram LLM Appointment Bot")
logger.info("=" * 60)
logger.info(f"Python version: {sys.version}")
logger.info(f"Debug mode: {settings.debug}")
logger.info(f"Log level: {settings.log_level}")
logger.info(f"Database URL: {settings.database_url_str.split('@')[0]}@***")
logger.info(f"Bot token configured: {'Yes' if settings.telegram_bot_token else 'No'}")
logger.info(f"Webhook URL: {settings.telegram_webhook_url or 'Not configured'}")
logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events:
    - Initializes database engine
    - Sets up Telegram webhook
    - Registers aiogram bot
    - Closes connections on shutdown
    """
    # Startup
    logger.info("🚀 Starting application...")

    try:
        # Check database connection
        logger.info("Checking database connection...")
        db_healthy = await check_database_connection()
        if db_healthy:
            logger.info("✅ Database connection verified")
        else:
            logger.error("❌ Database connection failed!")
            logger.warning("Application will start but database operations will fail")

        # Initialize Telegram webhook
        logger.info("Initializing Telegram webhook...")
        await startup_webhook()
        logger.info("✅ Telegram webhook initialized")

        logger.info("✅ Application startup complete")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error during startup: {e}", exc_info=True)
        logger.warning("Application will continue but may not function properly")

    yield

    # Shutdown
    logger.info("=" * 60)
    logger.info("🛑 Shutting down application...")

    try:
        # Close Telegram bot
        logger.info("Closing Telegram bot...")
        await shutdown_webhook()
        logger.info("✅ Telegram bot closed")

        # Close database connections
        logger.info("Closing database connections...")
        await close_database_connection()
        logger.info("✅ Database connections closed")

        logger.info("✅ Application shutdown complete")

    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}", exc_info=True)

    logger.info("=" * 60)


# Initialize FastAPI application
app = FastAPI(
    title="Telegram LLM Appointment Bot",
    description=(
        "Intelligent appointment booking bot powered by LLM. "
        "Handles natural language conversations for booking, "
        "rescheduling, and managing appointments."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """
    Root endpoint.

    Returns basic API information.
    """
    return {
        "message": "Telegram LLM Appointment Bot API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs" if settings.debug else "disabled in production",
            "telegram_webhook": "/telegram/webhook",
            "webhook_info": "/telegram/webhook/info",
        }
    }


@app.get("/health")
async def health_check():
    """
    Application health check endpoint.

    Checks:
    - API responsiveness
    - Database connectivity

    Returns:
        JSONResponse with health status
    """
    try:
        # Check database connection
        db_healthy = await check_database_connection()

        health_status = {
            "status": "healthy" if db_healthy else "degraded",
            "api": "operational",
            "database": "connected" if db_healthy else "disconnected",
            "version": "0.1.0",
        }

        status_code = 200 if db_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content=health_status
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "api": "operational",
                "database": "error",
                "error": str(e),
                "version": "0.1.0",
            }
        )


@app.get("/info")
async def app_info():
    """
    Application information endpoint.

    Returns configuration and status information.
    """
    return {
        "name": "Telegram LLM Appointment Bot",
        "version": "0.1.0",
        "environment": "development" if settings.debug else "production",
        "features": {
            "llm_powered": True,
            "async_operations": True,
            "database": "PostgreSQL",
            "bot_framework": "aiogram",
        },
        "capabilities": [
            "Natural language appointment booking",
            "Availability checking",
            "Appointment rescheduling",
            "Appointment cancellation",
            "Conversation history tracking",
        ]
    }


# Include bot webhook router
app.include_router(webhook_router)

logger.info("✅ FastAPI application initialized")
logger.info(f"📡 Webhook router mounted at: /telegram")

# If running with uvicorn directly (not through import)
if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("Starting uvicorn server...")
    logger.info(f"Host: {settings.app_host}")
    logger.info(f"Port: {settings.app_port}")
    logger.info("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
