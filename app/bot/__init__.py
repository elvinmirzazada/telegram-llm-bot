"""
Bot Module Initialization

Exports Telegram bot components for use across the application.
"""

from app.bot.webhook import (
    router as webhook_router,
    startup_webhook,
    shutdown_webhook,
    get_bots,
    get_dispatcher,
)
from app.bot.handlers import router as handlers_router

__all__ = [
    "webhook_router",
    "handlers_router",
    "startup_webhook",
    "shutdown_webhook",
    "get_bots",
    "get_dispatcher",
]
