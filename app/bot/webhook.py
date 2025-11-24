"""
Telegram Webhook Configuration

Handles webhook setup and FastAPI route integration for Telegram updates.
Dispatches incoming updates to aiogram handlers.
"""

import logging
import requests
from typing import Dict, Any, List

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from fastapi import APIRouter, Request, Response, HTTPException, Header
from fastapi.responses import JSONResponse
from app.db.session import get_db_context
from app.config import settings
from app.bot.handlers import router as handlers_router

logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter(prefix="/telegram", tags=["telegram"])

# Initialize Bot and Dispatcher
bots: Dict[str, Bot] = {}
dispatchers: Dict[str, Dispatcher] = {}


def get_bots() -> Dict[str, Bot]:
    """
    Get or create bot instance.

    Returns:
        Bots: Aiogram Bot instances
    """
    global bots
    if not bots:
        response = requests.get(settings.telegram_bots_endpoint, timeout=10)
        if response.status_code == 200:
            bot_tokens = response.json()
            if bot_tokens.get("success") and bot_tokens.get("data"):
                for token in bot_tokens.get('data', []):
                    bot_instance = Bot(token=token.get('bot_token', ''))
                    bots[token.get('chat_id', '')] = bot_instance
                    logger.info(f"Bot instance created for token: ****{token.get('bot_token')[:5]}")
                    dispatchers[token.get('chat_id', '')] = get_dispatcher(token.get('chat_id', ''))
                    logger.info(f"Bot dispatcher created for chat_id: {token.get('chat_id', '')}")

    return bots


def get_dispatcher(name: str) -> Dispatcher:
    """
    Get or create dispatcher instance.

    Returns:
        Dispatcher: Aiogram Dispatcher instance
    """
    if dispatchers:
        return dispatchers.get(name)
    dp = Dispatcher()
    # Register handlers router
    dp.include_router(handlers_router)
    return dp


@router.post("/webhook/{chat_id}")
async def telegram_webhook(
    request: Request,
    chat_id: str,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    f"""
    Handle incoming Telegram webhook updates.

    This endpoint receives updates from Telegram and dispatches them
    to the aiogram dispatcher for processing.

    Args:
        request: FastAPI request object
        x_telegram_bot_api_secret_token: Optional secret token for verification

    Returns:
        Response with status

    Example:
        POST /telegram/webhook/chat_id
        Body: Telegram Update JSON
        :param x_telegram_bot_api_secret_token:
        :param request:
        :param chat_id:
    """
    try:
        # Verify secret token if configured
        if settings.webhook_secret_token:
            if x_telegram_bot_api_secret_token != settings.webhook_secret_token:
                logger.warning("Invalid webhook secret token received")
                raise HTTPException(status_code=403, detail="Invalid secret token")

        # Parse request body
        try:
            update_data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook request body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Log incoming update (without sensitive data)
        update_id = update_data.get("update_id", "unknown")
        logger.info(f"Received webhook update #{update_id}")

        # Create Update object
        try:
            update = Update(**update_data)
        except Exception as e:
            logger.error(f"Failed to create Update object: {e}")
            raise HTTPException(status_code=400, detail="Invalid update format")

        # Get bot and dispatcher instances
        bot_instances = get_bots()
        dispatcher = get_dispatcher(chat_id)

        # Feed update to dispatcher
        bot_instance = bot_instances.get(chat_id)
        try:
            await dispatcher.feed_update(bot=bot_instance, update=update)
            logger.debug(f"Successfully processed update #{update_id}")
        except Exception as e:
            logger.error(f"Error processing update #{update_id}: {e}", exc_info=True)
            # Don't raise exception here - return 200 to Telegram to avoid retries
            # The error is logged and can be monitored

        # Always return 200 OK to Telegram
        return Response(status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook endpoint: {e}", exc_info=True)
        # Return 500 for unexpected errors
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook/info")
async def get_webhook_info() -> JSONResponse:
    """
    Get current webhook information from Telegram.

    Returns webhook status and configuration for monitoring/debugging.

    Returns:
        JSONResponse with webhook info

    Example:
        GET /telegram/webhook/info
    """
    try:
        bot_instances = get_bots()
        info = {}
        for chat_id, bot_instance in bot_instances.items():
            webhook_info = await bot_instance.get_webhook_info()

            info[chat_id] = {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": str(webhook_info.last_error_date) if webhook_info.last_error_date else None,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates,
            }

        logger.info("Webhook info retrieved successfully")
        return JSONResponse(content=info)

    except Exception as e:
        logger.error(f"Error getting webhook info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def setup_webhook(webhook_url: str | None = None) -> bool:
    """
    Setup webhook on application startup.

    Args:
        webhook_url: Webhook URL (uses settings if not provided)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        url = webhook_url or settings.telegram_webhook_url

        if not url:
            logger.warning("No webhook URL configured, skipping webhook setup")
            return False

        bot_instances = get_bots()

        for chat_id, bot_instance in bot_instances.items():
            # Delete existing webhook first
            await bot_instance.delete_webhook(drop_pending_updates=False)
            logger.info("Existing webhook deleted")
            webhook_url = url + f'/{chat_id}'
            # Set new webhook
            await bot_instance.set_webhook(
                url=webhook_url,
                drop_pending_updates=False,
                secret_token=settings.webhook_secret_token,
                allowed_updates=["message", "callback_query"],
            )

            logger.info(f"Webhook set successfully to: {webhook_url}")

            # Verify webhook was set
            webhook_info = await bot_instance.get_webhook_info()
            if webhook_info.url == webhook_url:
                logger.info("Webhook verification successful")
                return True
            else:
                logger.error(
                    f"Webhook verification failed. Expected: {webhook_url}, Got: {webhook_info.url}"
                )
        return False

    except Exception as e:
        logger.error(f"Failed to setup webhook: {e}", exc_info=True)
        return False


async def close_bot() -> None:
    """
    Close bot session on application shutdown.

    Should be called in FastAPI shutdown event.
    """
    global bots
    if bots:
        for chat_id, bot in bots.items():
            try:
                await bot.session.close()
                logger.info("Bot session closed successfully")
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")
            finally:
                bot = None


async def startup_webhook() -> None:
    """
    Startup handler for webhook initialization.

    Call this from FastAPI lifespan or startup event.
    """
    logger.info("Initializing Telegram webhook...")

    # Initialize bot and dispatcher
    get_bots()

    # Setup webhook if URL is configured
    success = await setup_webhook()
    if success:
        logger.info("Telegram webhook initialized successfully")
    else:
        logger.error("Failed to initialize Telegram webhook")


async def shutdown_webhook() -> None:
    """
    Shutdown handler for webhook cleanup.

    Call this from FastAPI lifespan or shutdown event.
    """
    logger.info("Shutting down Telegram webhook...")
    await close_bot()
    logger.info("Telegram webhook shutdown complete")


# Health check endpoint for the bot
@router.get("/health")
async def bot_health_check() -> JSONResponse:
    """
    Health check endpoint for bot status.

    Returns:
        JSONResponse with bot health status
    """
    try:
        bot_instances = get_bots()
        body = {}
        # Try to get bot info
        for chat_id, bot_instance in bot_instances.items():
            bot_info = await bot_instance.get_me()
            body[chat_id] = {
                "status": "healthy",
                "bot_username": bot_info.username,
                "bot_id": bot_info.id,
                "bot_name": bot_info.first_name,
            }

        return JSONResponse(content=body)

    except Exception as e:
        logger.error(f"Bot health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )


# Export for use in main FastAPI app
__all__ = [
    "router",
    "startup_webhook",
    "shutdown_webhook",
    "get_bots",
    "get_dispatcher",
]
