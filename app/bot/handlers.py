"""
Telegram Bot Message Handlers

Implements aiogram handlers for processing user messages and commands.
Orchestrates LLM service and appointment service for intelligent responses.
"""

import logging
from typing import Any, Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.repository import ConversationRepository, CustomerRepository
from app.services.local_llm import LocalLLMService, LocalLLMError
from app.services.appointment import AppointmentService, AppointmentServiceError

logger = logging.getLogger(__name__)

# Create router for handlers
router = Router(name="main_router")


# Conversation state storage (in production, use Redis or similar)
conversation_states: Dict[int, Dict[str, Any]] = {}


def get_telegram_user_dict(message: Message) -> Dict[str, Any]:
    """
    Extract user information from Telegram message.

    Args:
        message: Aiogram Message object

    Returns:
        Dictionary with user information
    """
    return {
        "telegram_id": str(message.from_user.id),
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "language_code": message.from_user.language_code,
    }


async def get_or_create_conversation_state(
    user_id: int,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Retrieve or create conversation state for user.

    Args:
        user_id: Telegram user ID
        db: Database session

    Returns:
        Conversation state dictionary
    """
    if user_id not in conversation_states:
        # Initialize new conversation state
        customer_repo = CustomerRepository(db)
        customer = await customer_repo.get_customer_by_telegram_id(str(user_id))

        conversation_states[user_id] = {
            "customer_id": customer["id"] if customer else None,
            "history": [],
            "last_intent": None,
            "pending_action": None,
            "context": {},
        }

        logger.info(f"Created new conversation state for user {user_id}")

    return conversation_states[user_id]


async def save_conversation_message(
    db: AsyncSession,
    customer_id: Optional[int],
    message_text: str,
    message_type: str,
    context_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save conversation message to database.

    Args:
        db: Database session
        customer_id: Customer ID (if exists)
        message_text: Message content
        message_type: "user" or "bot"
        context_data: Additional context
    """
    if customer_id:
        try:
            conversation_repo = ConversationRepository(db)
            await conversation_repo.save_message(
                customer_id=customer_id,
                message_text=message_text,
                message_type=message_type,
                context_data=context_data,
            )
        except Exception as e:
            logger.error(f"Failed to save conversation message: {e}")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Handle /start command.

    Welcomes new users and explains bot capabilities.

    Args:
        message: Incoming message
    """
    customer = None
    try:
        user = message.from_user
        telegram_user = get_telegram_user_dict(message)

        logger.info(f"User {user.id} ({user.username}) started the bot")

        # Get database session
        async for db in get_db_session():
            # Get or create customer
            customer_repo = CustomerRepository(db)
            customer = await customer_repo.get_customer_by_telegram_id(
                str(user.id)
            )

            if not customer:
                # Create new customer
                customer = await customer_repo.create_customer(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                logger.info(f"Created new customer record for user {user.id}")

            # Initialize conversation state
            conversation_states[user.id] = {
                "customer_id": customer["id"],
                "history": [],
                "last_intent": None,
                "pending_action": None,
                "context": {},
            }

            # Save welcome message
            await save_conversation_message(
                db, customer["id"], "/start", "user"
            )

            break

        welcome_message = (
            f"👋 Hello{' ' + user.first_name if user.first_name else ''}!\n\n"
            f"I'm your intelligent appointment booking assistant. "
            f"I can help you:\n\n"
            f"📅 Book new appointments\n"
            f"🔍 Check available time slots\n"
            f"✏️ Reschedule existing appointments\n"
            f"❌ Cancel appointments\n"
            f"📋 View your upcoming appointments\n\n"
            f"Just tell me what you need in natural language, and I'll assist you!\n\n"
            f"💡 Examples:\n"
            f"• \"I want to book an appointment tomorrow at 2pm\"\n"
            f"• \"What times are available on Friday?\"\n"
            f"• \"Show me my appointments\"\n"
            f"• \"Cancel my appointment on Monday\"\n\n"
            f"Our business hours: Monday-Friday, 9:00 AM - 5:00 PM"
        )

        await message.answer(welcome_message)

        # Save bot response
        async for db in get_db_session():
            await save_conversation_message(
                db, customer["id"], welcome_message, "bot"
            )
            break

    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await message.answer(
            "Welcome! I'm having a small issue, but I'm ready to help you. "
            "What can I do for you today?"
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Handle /help command.

    Provides usage instructions and examples.

    Args:
        message: Incoming message
    """
    try:
        help_message = (
            "🤖 **Appointment Bot Help**\n\n"
            "**Available Commands:**\n"
            "/start - Start the bot and register\n"
            "/help - Show this help message\n"
            "/myappointments - View your appointments\n"
            "/cancel - Cancel the current operation\n\n"
            "**How to Use:**\n\n"
            "📅 **Book an appointment:**\n"
            "Just tell me when you'd like to come in!\n"
            "Example: \"Book me for tomorrow at 2pm\"\n\n"
            "🔍 **Check availability:**\n"
            "Ask what times are free.\n"
            "Example: \"What's available on Friday?\"\n\n"
            "✏️ **Reschedule:**\n"
            "Let me know you want to change your appointment.\n"
            "Example: \"Reschedule my Monday appointment to Tuesday at 3pm\"\n\n"
            "❌ **Cancel:**\n"
            "Just say you want to cancel.\n"
            "Example: \"Cancel my appointment\"\n\n"
            "**Business Hours:**\n"
            "Monday - Friday: 9:00 AM - 5:00 PM\n"
            "Appointments available in 30-minute slots.\n\n"
            "Need help? Just ask!"
        )

        await message.answer(help_message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        await message.answer("Here to help! Ask me anything about appointments.")


@router.message(Command("myappointments"))
async def cmd_my_appointments(message: Message) -> None:
    """
    Handle /myappointments command.

    Shows user's upcoming appointments.

    Args:
        message: Incoming message
    """
    try:
        telegram_user = get_telegram_user_dict(message)

        async for db in get_db_session():
            appointment_service = AppointmentService(db)

            # Get appointments
            result = await appointment_service.get_customer_appointments(
                telegram_user=telegram_user,
                status="pending",
            )

            await message.answer(result["message"])
            break

    except Exception as e:
        logger.error(f"Error fetching appointments: {e}", exc_info=True)
        await message.answer(
            "I'm having trouble retrieving your appointments right now. "
            "Please try again in a moment."
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    """
    Handle /cancel command.

    Cancels current operation and clears conversation state.

    Args:
        message: Incoming message
    """
    try:
        user_id = message.from_user.id

        if user_id in conversation_states:
            conversation_states[user_id]["pending_action"] = None
            conversation_states[user_id]["context"] = {}

        await message.answer(
            "✅ Operation cancelled. How else can I help you?"
        )

    except Exception as e:
        logger.error(f"Error in cancel command: {e}", exc_info=True)
        await message.answer("Operation cancelled.")


@router.message(F.text)
async def handle_text_message(message: Message) -> None:
    """
    Handle all text messages.

    Main message handler that orchestrates:
    1. Conversation state retrieval
    2. LLM processing
    3. Intent handling via appointment service
    4. Database operations
    5. User response

    Args:
        message: Incoming message
    """
    user = message.from_user
    user_text = message.text

    logger.info(f"Received message from user {user.id}: {user_text[:100]}")

    try:
        telegram_user = get_telegram_user_dict(message)
        await message.answer("Preparing an answer, please wait...")
        # Show typing indicator
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )

        # Get database session - use single iteration properly
        db_generator = get_db_session()
        db = await db_generator.__anext__()

        try:
            # Get or create conversation state
            conversation_state = await get_or_create_conversation_state(
                user.id, db
            )

            # Add message to history
            conversation_state["history"].append({
                "role": "user",
                "content": user_text,
                "timestamp": message.date.isoformat() if message.date else None,
            })

            # Save user message to database
            await save_conversation_message(
                db,
                conversation_state.get("customer_id"),
                user_text,
                "user",
                context_data={"message_id": message.message_id},
            )

            # Initialize services
            llm_service = LocalLLMService(
                repository_callback=create_repository_callback(db)
            )
            appointment_service = AppointmentService(db)

            try:
                # Send to LLM for processing
                logger.info(f"Sending message to LLM service for user {user.id}")
                llm_response = await llm_service.generate_response(
                    message=user_text,
                    conversation_state=conversation_state,
                )

                logger.info(
                    f"LLM response - Intent: {llm_response.get('intent')}, "
                    f"Confidence: {llm_response.get('confidence')}"
                )

                # Parse LLM output
                parsed_data = await appointment_service.parse_llm_output(
                    raw_response=llm_response if isinstance(llm_response, str)
                    else str(llm_response)
                )

                # Update conversation state
                conversation_state["last_intent"] = parsed_data.get("intent")

                # Handle different intents
                intent = parsed_data.get("intent")

                if intent == "book_appointment":
                    logger.info(f"Handling booking intent for user {user.id}")
                    result = await appointment_service.handle_booking_intent(
                        parsed_data=parsed_data,
                        db=db,
                        telegram_user=telegram_user,
                    )
                    response_message = result["message"]

                elif intent == "check_availability":
                    logger.info(f"Handling availability intent for user {user.id}")
                    result = await appointment_service.handle_availability_intent(
                        parsed_data=parsed_data,
                        db=db,
                    )
                    response_message = result["message"]

                elif intent == "reschedule_appointment":
                    logger.info(f"Handling reschedule intent for user {user.id}")
                    result = await appointment_service.handle_reschedule_intent(
                        parsed_data=parsed_data,
                        db=db,
                        telegram_user=telegram_user,
                    )
                    response_message = result["message"]

                elif intent == "cancel_appointment":
                    logger.info(f"Handling cancel intent for user {user.id}")
                    result = await appointment_service.handle_cancel_intent(
                        parsed_data=parsed_data,
                        db=db,
                        telegram_user=telegram_user,
                    )
                    response_message = result["message"]

                elif intent == "smalltalk":
                    logger.info(f"Handling smalltalk for user {user.id}")
                    # Use LLM's generated response for smalltalk
                    response_message = parsed_data.get(
                        "user_message",
                        "I'm here to help you with appointments! "
                        "You can book, check availability, reschedule, or cancel appointments."
                    )

                else:
                    logger.warning(f"Unknown intent: {intent}")
                    response_message = (
                        "I'm not quite sure what you'd like to do. "
                        "Could you please rephrase? I can help you book, "
                        "check availability, reschedule, or cancel appointments."
                    )

                # Send response to user (ONCE)
                if response_message:
                    await message.answer(response_message)

                    # Save bot response
                    await save_conversation_message(
                        db,
                        conversation_state.get("customer_id"),
                        response_message,
                        "bot",
                        context_data={
                            "intent": intent,
                            "confidence": parsed_data.get("confidence"),
                        },
                    )

                    # Add to conversation history
                    conversation_state["history"].append({
                        "role": "assistant",
                        "content": response_message,
                    })

                    # Limit history to last 10 messages
                    if len(conversation_state["history"]) > 10:
                        conversation_state["history"] = conversation_state["history"][-10:]

            except LocalLLMError as e:
                logger.error(f"LLM error for user {user.id}: {e}")
                await message.answer(
                    "I'm having trouble processing your request right now. "
                    "Could you please try again? If the problem persists, "
                    "try using simpler language or contact support."
                )

            except AppointmentServiceError as e:
                logger.error(f"Appointment service error for user {user.id}: {e}")
                await message.answer(
                    "There was an issue processing your appointment request. "
                    "Please try again or contact support if the problem continues."
                )

        finally:
            # Properly close the database session
            try:
                await db_generator.aclose()
            except:
                pass

    except Exception as e:
        logger.error(
            f"Unexpected error handling message from user {user.id}: {e}",
            exc_info=True
        )
        await message.answer(
            "😔 I encountered an unexpected error. Please try again.\n\n"
            "If you continue to have issues, please contact support or try:\n"
            "• Using /start to restart\n"
            "• Simplifying your request\n"
            "• Trying again in a few moments"
        )


def create_repository_callback(db: AsyncSession):
    """
    Create repository callback function for LLM service.

    This allows the LLM service to fetch data from repositories.

    Args:
        db: Database session

    Returns:
        Async callback function
    """
    from app.db.repository import AppointmentRepository

    async def repository_callback(operation: str, **kwargs):
        """
        Repository callback for LLM service.

        Args:
            operation: Operation name (e.g., "get_available_slots")
            **kwargs: Operation parameters

        Returns:
            Operation result
        """
        try:
            repo = AppointmentRepository(db)

            if operation == "get_available_slots":
                return await repo.get_available_slots(
                    date=kwargs.get("date"),
                    duration_minutes=kwargs.get("duration_minutes", 30),
                )
            elif operation == "get_appointment_by_id":
                return await repo.get_appointment_by_id(
                    kwargs.get("appointment_id")
                )
            else:
                logger.warning(f"Unknown repository operation: {operation}")
                return None

        except Exception as e:
            logger.error(f"Repository callback error: {e}")
            return None

    return repository_callback


@router.message(F.content_type.in_(["photo", "video", "document", "audio", "voice"]))
async def handle_media_message(message: Message) -> None:
    """
    Handle media messages (photos, videos, etc.).

    Args:
        message: Incoming message with media
    """
    try:
        await message.answer(
            "I can only process text messages right now. "
            "Please describe what you'd like to do with your appointment."
        )
    except Exception as e:
        logger.error(f"Error handling media message: {e}")


@router.message()
async def handle_other_messages(message: Message) -> None:
    """
    Fallback handler for any other message types.

    Args:
        message: Incoming message
    """
    try:
        await message.answer(
            "I'm not sure how to handle that type of message. "
            "Please send a text message describing what you need."
        )
    except Exception as e:
        logger.error(f"Error in fallback handler: {e}")
