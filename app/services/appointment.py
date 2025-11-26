"""
Appointment Service

Business logic for appointment booking, management, and validation.
Consumes LLM JSON output and orchestrates repository operations.
"""

import json
import logging
from datetime import datetime, date, time, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import (
    AppointmentRepository,
    CustomerRepository,
    DatabaseError,
)

logger = logging.getLogger(__name__)


class AppointmentServiceError(Exception):
    """Custom exception for appointment service errors."""
    pass


class AppointmentService:
    """
    Service for managing appointment business logic.

    Consumes LLM output and orchestrates database operations through repositories.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize AppointmentService.

        Args:
            db_session: Async database session
        """
        self.db = db_session
        self.appointment_repo = AppointmentRepository(db_session)
        self.customer_repo = CustomerRepository(db_session)

        logger.info("AppointmentService initialized")

    async def parse_llm_output(self, raw_response: str) -> Dict[str, Any]:
        """
        Parse and validate LLM JSON output.

        Args:
            raw_response: Raw JSON string from LLM

        Returns:
            Parsed and validated dictionary

        Raises:
            AppointmentServiceError: If parsing fails or JSON is invalid

        Example:
            >>> service = AppointmentService(db)
            >>> data = await service.parse_llm_output(llm_response)
            >>> print(data["intent"])
            "book_appointment"
        """
        try:
            # Parse JSON
            parsed_data = json.loads(raw_response)
            print(parsed_data)
            # Validate required fields
            if "intent" not in parsed_data:
                raise ValueError("Missing required field: intent")

            # Normalize intent
            valid_intents = [
                "book_appointment",
                "check_availability",
                "reschedule_appointment",
                "cancel_appointment",
                "smalltalk",
            ]

            intent = parsed_data.get("intent")
            if intent not in valid_intents:
                logger.warning(f"Unknown intent: {intent}, treating as smalltalk")
                parsed_data["intent"] = "smalltalk"

            # Extract and normalize entities from different possible field names
            entities = parsed_data.get("entities", {})

            # Map various field names to standardized format
            parsed_data["requested_date"] = (
                entities.get("date") or
                parsed_data.get("requested_date") or
                parsed_data.get("date")
            )

            parsed_data["requested_time"] = (
                entities.get("time") or
                parsed_data.get("requested_time") or
                parsed_data.get("time")
            )

            parsed_data["customer_name"] = (
                parsed_data.get("customer_name") or
                parsed_data.get("name")
            )

            parsed_data["notes"] = (
                parsed_data.get("notes") or
                entities.get("notes") or
                ""
            )

            parsed_data["appointment_id"] = (
                entities.get("appointment_id") or
                parsed_data.get("appointment_id")
            )

            parsed_data["service_type"] = entities.get("service_type")

            # Extract user message for response
            parsed_data["user_message"] = parsed_data.get(
                "user_message",
                "I'm processing your request..."
            )

            # Extract action
            parsed_data["action"] = parsed_data.get("action", "proceed")

            # Extract confidence
            parsed_data["confidence"] = parsed_data.get("confidence", 0.5)

            logger.debug(f"Parsed LLM output - Intent: {parsed_data['intent']}")

            return parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM output as JSON: {e}")
            raise AppointmentServiceError(
                f"Invalid JSON from LLM: {str(e)}"
            ) from e
        except Exception as e:
            logger.error(f"Error parsing LLM output: {e}")
            raise AppointmentServiceError(
                f"Failed to parse LLM output: {str(e)}"
            ) from e

    async def handle_booking_intent(
        self,
        parsed_data: Dict[str, Any],
        db: AsyncSession,
        telegram_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle appointment booking intent.

        Validates slot availability and creates appointment.

        Args:
            parsed_data: Parsed LLM output containing booking details
            db: Database session
            telegram_user: Telegram user information dict with keys:
                - telegram_id: User's Telegram ID
                - username: Username (optional)
                - first_name: First name (optional)
                - last_name: Last name (optional)

        Returns:
            Dictionary formatted for Telegram reply with keys:
                - success: Boolean
                - message: User-facing message
                - appointment: Appointment details (if successful)
                - available_slots: Alternative slots (if requested slot unavailable)

        Example:
            >>> result = await service.handle_booking_intent(
            ...     parsed_data,
            ...     db,
            ...     {"telegram_id": "123456", "first_name": "John"}
            ... )
            >>> print(result["message"])
            "Your appointment has been booked for..."
        """
        try:
            requested_date = parsed_data.get("requested_date")
            requested_time = parsed_data.get("requested_time")
            notes = parsed_data.get("notes", "")

            # Check for missing information
            missing_info = []
            if not requested_date:
                missing_info.append("date")
            if not requested_time:
                missing_info.append("time")

            if missing_info:
                return {
                    "success": False,
                    "message": (
                        f"To book your appointment, I need the following information: "
                        f"{', '.join(missing_info)}. "
                        f"{parsed_data.get('user_message', 'Please provide the missing details.')}"
                    ),
                    "missing_info": missing_info,
                    "action": "ask_clarification",
                }

            # Validate date and time format
            try:
                appointment_date = datetime.strptime(requested_date, "%Y-%m-%d").date()
                appointment_time_obj = datetime.strptime(requested_time, "%H:%M").time()
            except ValueError as e:
                logger.error(f"Invalid date/time format: {e}")
                return {
                    "success": False,
                    "message": (
                        "The date or time format appears to be invalid. "
                        "Please provide the date (e.g., 'November 25' or '2025-11-25') "
                        "and time (e.g., '2:00 PM' or '14:00')."
                    ),
                    "error": "invalid_format",
                }

            # Validate appointment is in the future
            appointment_datetime = datetime.combine(appointment_date, appointment_time_obj)
            if appointment_datetime <= datetime.now():
                return {
                    "success": False,
                    "message": (
                        "The requested time has already passed. "
                        "Please choose a future date and time."
                    ),
                    "error": "past_datetime",
                }

            # # Validate business hours (9 AM - 5 PM, Monday-Friday)
            # if appointment_date.weekday() >= 5:  # Weekend
            #     return {
            #         "success": False,
            #         "message": (
            #             "We're only open Monday through Friday. "
            #             "Please choose a weekday for your appointment."
            #         ),
            #         "error": "weekend",
            #     }

            # business_start = time(9, 0)
            # business_end = time(17, 0)
            #
            # if appointment_time_obj < business_start or appointment_time_obj >= business_end:
            #     return {
            #         "success": False,
            #         "message": (
            #             "Our business hours are 9:00 AM to 5:00 PM. "
            #             "Please choose a time within these hours."
            #         ),
            #         "error": "outside_business_hours",
            #     }

            # Get or create customer
            telegram_id = str(telegram_user.get("telegram_id"))
            customer = await self.customer_repo.get_customer_by_telegram_id(telegram_id)

            if not customer:
                # Create new customer
                logger.info(f"Creating new customer for telegram_id: {telegram_id}")
                customer = await self.customer_repo.create_customer(
                    telegram_id=telegram_id,
                    username=telegram_user.get("username"),
                    first_name=telegram_user.get("first_name"),
                    last_name=telegram_user.get("last_name"),
                )

            customer_id = customer["id"]

            # Check availability for the requested slot
            logger.info(f"Checking availability for {requested_date} at {requested_time}")
            # available_slots = await self.appointment_repo.get_available_slots(
            #     date=appointment_date,
            #     duration_minutes=30,
            # )

            # Check if requested time is available
            is_slot_available = True
            # any(
            #     slot.get("slot_time") == requested_time and slot.get("available", False)
            #     for slot in available_slots
            # )

            if not is_slot_available:
                logger.warning(
                    f"Requested slot {requested_date} {requested_time} is not available"
                )

                # Find alternative slots
                alternative_slots = [
                    slot for slot in available_slots
                    if slot.get("available", False)
                ][:5]  # Show up to 5 alternatives

                slots_text = "\n".join([
                    f"  • {slot['slot_time']}"
                    for slot in alternative_slots
                ]) if alternative_slots else "  No slots available"

                return {
                    "success": False,
                    "message": (
                        f"Unfortunately, {requested_time} on {appointment_date.strftime('%B %d, %Y')} "
                        f"is not available.\n\n"
                        f"Available times on that day:\n{slots_text}\n\n"
                        f"Would you like to book one of these times instead?"
                    ),
                    "available_slots": alternative_slots,
                    "requested_date": requested_date,
                    "error": "slot_unavailable",
                }

            # Create the appointment
            logger.info(
                f"Creating appointment for customer {customer_id} "
                f"on {requested_date} at {requested_time}"
            )

            # appointment = await self.appointment_repo.create_appointment(
            #     customer_id=customer_id,
            #     date=requested_date,
            #     time=requested_time,
            #     notes=notes or "Booked via Telegram bot",
            # )

            # Format success response
            date_formatted = appointment_date.strftime("%A, %B %d, %Y")
            time_formatted = appointment_time_obj.strftime("%I:%M %p")

            return {
                "success": True,
                "message": (
                    f"✅ Your appointment has been successfully booked!\n\n"
                    f"📅 Date: {date_formatted}\n"
                    f"🕒 Time: {time_formatted}\n"
                    f"📝 Confirmation ID: #{appointment['id']}\n\n"
                    f"We'll send you a reminder before your appointment. "
                    f"If you need to reschedule or cancel, just let me know!"
                ),
                "appointment": {
                    "id": appointment["id"],
                    "date": requested_date,
                    "time": requested_time,
                    "status": appointment.get("status", "pending"),
                    "customer_id": customer_id,
                },
            }

        except DatabaseError as e:
            logger.error(f"Database error during booking: {e}")
            return {
                "success": False,
                "message": (
                    "I'm sorry, there was a problem booking your appointment. "
                    "Please try again in a moment."
                ),
                "error": "database_error",
            }
        except Exception as e:
            logger.error(f"Unexpected error during booking: {e}")
            return {
                "success": False,
                "message": (
                    "An unexpected error occurred. "
                    "Please try again or contact support if the problem persists."
                ),
                "error": "unexpected_error",
            }

    async def handle_reschedule_intent(
        self,
        parsed_data: Dict[str, Any],
        db: AsyncSession,
        telegram_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle appointment rescheduling intent.

        Args:
            parsed_data: Parsed LLM output containing reschedule details
            db: Database session
            telegram_user: Telegram user information

        Returns:
            Dictionary formatted for Telegram reply

        Example:
            >>> result = await service.handle_reschedule_intent(
            ...     {"appointment_id": 123, "requested_date": "2025-11-25"},
            ...     db,
            ...     telegram_user
            ... )
        """
        try:
            appointment_id = parsed_data.get("appointment_id")
            new_date = parsed_data.get("requested_date")
            new_time = parsed_data.get("requested_time")

            # Get customer
            telegram_id = str(telegram_user.get("telegram_id"))
            customer = await self.customer_repo.get_customer_by_telegram_id(telegram_id)

            if not customer:
                return {
                    "success": False,
                    "message": (
                        "I couldn't find your customer record. "
                        "Please contact support for assistance."
                    ),
                    "error": "customer_not_found",
                }

            # If no appointment ID provided, show user's appointments
            if not appointment_id:
                appointments = await self.appointment_repo.get_customer_appointments(
                    customer_id=customer["id"],
                    status="pending",
                )

                if not appointments:
                    return {
                        "success": False,
                        "message": (
                            "You don't have any upcoming appointments to reschedule. "
                            "Would you like to book a new appointment instead?"
                        ),
                        "appointments": [],
                    }

                # Format appointments list
                appointments_text = "\n".join([
                    f"  {i+1}. #{apt['id']} - {apt['appointment_date']} at {apt['appointment_time']}"
                    for i, apt in enumerate(appointments)
                ])

                return {
                    "success": False,
                    "message": (
                        f"Which appointment would you like to reschedule?\n\n"
                        f"{appointments_text}\n\n"
                        f"Please reply with the confirmation number (e.g., #123) "
                        f"or the date and time."
                    ),
                    "appointments": appointments,
                    "action": "ask_clarification",
                }

            # Get the appointment
            appointment = await self.appointment_repo.get_appointment_by_id(appointment_id)

            if not appointment:
                return {
                    "success": False,
                    "message": (
                        f"I couldn't find appointment #{appointment_id}. "
                        f"Please check the confirmation number and try again."
                    ),
                    "error": "appointment_not_found",
                }

            # Verify ownership
            if appointment["customer_id"] != customer["id"]:
                return {
                    "success": False,
                    "message": (
                        "This appointment doesn't belong to you. "
                        "Please provide your own appointment details."
                    ),
                    "error": "unauthorized",
                }

            # Check if new date/time provided
            if not new_date or not new_time:
                old_date = appointment["appointment_date"]
                old_time = appointment["appointment_time"]

                return {
                    "success": False,
                    "message": (
                        f"I found your appointment on {old_date} at {old_time}.\n\n"
                        f"What date and time would you like to reschedule it to?"
                    ),
                    "current_appointment": appointment,
                    "action": "ask_clarification",
                }

            # Cancel old appointment and create new one
            # (This is a simplified approach - in production, you might want to UPDATE instead)
            await self.appointment_repo.update_appointment_status(
                appointment_id, "cancelled"
            )

            # Create new appointment (reuse booking logic)
            parsed_data["intent"] = "book_appointment"
            booking_result = await self.handle_booking_intent(
                parsed_data, db, telegram_user
            )

            if booking_result["success"]:
                booking_result["message"] = (
                    f"✅ Your appointment has been rescheduled!\n\n"
                    f"Old appointment (#{appointment_id}) has been cancelled.\n"
                    f"{booking_result['message']}"
                )
                booking_result["old_appointment_id"] = appointment_id

            return booking_result

        except Exception as e:
            logger.error(f"Error handling reschedule: {e}")
            return {
                "success": False,
                "message": (
                    "I'm sorry, there was a problem rescheduling your appointment. "
                    "Please try again."
                ),
                "error": "reschedule_error",
            }

    async def handle_cancel_intent(
        self,
        parsed_data: Dict[str, Any],
        db: AsyncSession,
        telegram_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle appointment cancellation intent.

        Args:
            parsed_data: Parsed LLM output containing cancellation details
            db: Database session
            telegram_user: Telegram user information

        Returns:
            Dictionary formatted for Telegram reply

        Example:
            >>> result = await service.handle_cancel_intent(
            ...     {"appointment_id": 123},
            ...     db,
            ...     telegram_user
            ... )
        """
        try:
            appointment_id = parsed_data.get("appointment_id")

            # Get customer
            telegram_id = str(telegram_user.get("telegram_id"))
            customer = await self.customer_repo.get_customer_by_telegram_id(telegram_id)

            if not customer:
                return {
                    "success": False,
                    "message": (
                        "I couldn't find your customer record. "
                        "Please contact support for assistance."
                    ),
                    "error": "customer_not_found",
                }

            # If no appointment ID, show list of appointments
            if not appointment_id:
                appointments = await self.appointment_repo.get_customer_appointments(
                    customer_id=customer["id"],
                    status="pending",
                )

                if not appointments:
                    return {
                        "success": False,
                        "message": (
                            "You don't have any upcoming appointments to cancel."
                        ),
                        "appointments": [],
                    }

                # Format appointments list
                appointments_text = "\n".join([
                    f"  {i+1}. #{apt['id']} - {apt['appointment_date']} at {apt['appointment_time']}"
                    for i, apt in enumerate(appointments)
                ])

                return {
                    "success": False,
                    "message": (
                        f"Which appointment would you like to cancel?\n\n"
                        f"{appointments_text}\n\n"
                        f"Please reply with the confirmation number (e.g., #123)."
                    ),
                    "appointments": appointments,
                    "action": "ask_clarification",
                }

            # Get the appointment
            appointment = await self.appointment_repo.get_appointment_by_id(appointment_id)

            if not appointment:
                return {
                    "success": False,
                    "message": (
                        f"I couldn't find appointment #{appointment_id}. "
                        f"Please check the confirmation number and try again."
                    ),
                    "error": "appointment_not_found",
                }

            # Verify ownership
            if appointment["customer_id"] != customer["id"]:
                return {
                    "success": False,
                    "message": (
                        "This appointment doesn't belong to you. "
                        "Please provide your own appointment details."
                    ),
                    "error": "unauthorized",
                }

            # Check if already cancelled
            if appointment["status"] == "cancelled":
                return {
                    "success": False,
                    "message": (
                        f"Appointment #{appointment_id} has already been cancelled."
                    ),
                    "error": "already_cancelled",
                }

            # Cancel the appointment
            success = await self.appointment_repo.update_appointment_status(
                appointment_id, "cancelled"
            )

            if success:
                date_str = appointment["appointment_date"]
                time_str = appointment["appointment_time"]

                return {
                    "success": True,
                    "message": (
                        f"✅ Your appointment has been cancelled.\n\n"
                        f"Cancelled appointment:\n"
                        f"📅 Date: {date_str}\n"
                        f"🕒 Time: {time_str}\n"
                        f"📝 Confirmation ID: #{appointment_id}\n\n"
                        f"If you'd like to book a new appointment, just let me know!"
                    ),
                    "cancelled_appointment": appointment,
                }
            else:
                return {
                    "success": False,
                    "message": (
                        "There was a problem cancelling your appointment. "
                        "Please try again or contact support."
                    ),
                    "error": "cancellation_failed",
                }

        except Exception as e:
            logger.error(f"Error handling cancellation: {e}")
            return {
                "success": False,
                "message": (
                    "I'm sorry, there was a problem cancelling your appointment. "
                    "Please try again."
                ),
                "error": "cancel_error",
            }

    async def handle_availability_intent(
        self,
        parsed_data: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Handle availability check intent.

        Args:
            parsed_data: Parsed LLM output containing date to check
            db: Database session

        Returns:
            Dictionary formatted for Telegram reply with available slots

        Example:
            >>> result = await service.handle_availability_intent(
            ...     {"requested_date": "2025-11-25"},
            ...     db
            ... )
            >>> print(result["available_slots"])
        """
        try:
            requested_date = parsed_data.get("requested_date")

            if not requested_date:
                return {
                    "success": False,
                    "message": (
                        "Which date would you like to check availability for? "
                        "You can say something like 'tomorrow', 'next Monday', or 'November 25th'."
                    ),
                    "action": "ask_clarification",
                }

            # Parse date
            try:
                check_date = datetime.strptime(requested_date, "%Y-%m-%d").date()
            except ValueError:
                return {
                    "success": False,
                    "message": (
                        "I couldn't understand that date. "
                        "Please provide a valid date like 'tomorrow' or 'November 25, 2025'."
                    ),
                    "error": "invalid_date",
                }

            # Check if date is in the past
            if check_date < date.today():
                return {
                    "success": False,
                    "message": (
                        "That date has already passed. "
                        "Please choose a future date."
                    ),
                    "error": "past_date",
                }

            # Check if weekend
            if check_date.weekday() >= 5:
                return {
                    "success": False,
                    "message": (
                        f"{check_date.strftime('%A, %B %d')} is a weekend. "
                        f"We're only open Monday through Friday. "
                        f"Would you like to check a weekday instead?"
                    ),
                    "error": "weekend",
                }

            # Get available slots
            logger.info(f"Checking availability for {requested_date}")
            available_slots = await self.appointment_repo.get_available_slots(
                date=check_date,
                duration_minutes=30,
            )

            # Filter only available slots
            free_slots = [
                slot for slot in available_slots
                if slot.get("available", False)
            ]

            if not free_slots:
                return {
                    "success": True,
                    "message": (
                        f"Unfortunately, there are no available slots on "
                        f"{check_date.strftime('%A, %B %d, %Y')}.\n\n"
                        f"Would you like to check a different date?"
                    ),
                    "available_slots": [],
                    "date": requested_date,
                }

            # Format slots for display
            # Group into morning, afternoon, late afternoon
            morning_slots = []
            afternoon_slots = []
            late_slots = []

            for slot in free_slots:
                slot_time = slot.get("slot_time", "")
                hour = int(slot_time.split(":")[0]) if slot_time else 0

                if hour < 12:
                    morning_slots.append(slot_time)
                elif hour < 15:
                    afternoon_slots.append(slot_time)
                else:
                    late_slots.append(slot_time)

            message_parts = [
                f"📅 Available times for {check_date.strftime('%A, %B %d, %Y')}:\n"
            ]

            if morning_slots:
                slots_text = ", ".join(morning_slots)
                message_parts.append(f"🌅 Morning: {slots_text}")

            if afternoon_slots:
                slots_text = ", ".join(afternoon_slots)
                message_parts.append(f"☀️ Afternoon: {slots_text}")

            if late_slots:
                slots_text = ", ".join(late_slots)
                message_parts.append(f"🌆 Late Afternoon: {slots_text}")

            message_parts.append(
                "\nWould you like to book one of these times?"
            )

            return {
                "success": True,
                "message": "\n".join(message_parts),
                "available_slots": free_slots,
                "date": requested_date,
                "slots_count": len(free_slots),
            }

        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {
                "success": False,
                "message": (
                    "I'm sorry, there was a problem checking availability. "
                    "Please try again."
                ),
                "error": "availability_error",
            }

    async def get_customer_appointments(
        self,
        telegram_user: Dict[str, Any],
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get all appointments for a customer.

        Args:
            telegram_user: Telegram user information
            status: Optional status filter

        Returns:
            Dictionary with appointments list

        Example:
            >>> result = await service.get_customer_appointments(telegram_user)
        """
        try:
            telegram_id = str(telegram_user.get("telegram_id"))
            customer = await self.customer_repo.get_customer_by_telegram_id(telegram_id)

            if not customer:
                return {
                    "success": False,
                    "message": "No customer record found.",
                    "appointments": [],
                }

            appointments = await self.appointment_repo.get_customer_appointments(
                customer_id=customer["id"],
                status=status,
            )

            if not appointments:
                status_text = f" {status}" if status else ""
                return {
                    "success": True,
                    "message": f"You don't have any{status_text} appointments.",
                    "appointments": [],
                }

            # Format appointments
            appointments_text = []
            for apt in appointments:
                date_str = apt["appointment_date"]
                time_str = apt["appointment_time"]
                status_emoji = {
                    "pending": "⏳",
                    "confirmed": "✅",
                    "cancelled": "❌",
                    "completed": "✔️",
                }.get(apt["status"], "📅")

                appointments_text.append(
                    f"{status_emoji} #{apt['id']} - {date_str} at {time_str} ({apt['status']})"
                )

            message = "Your appointments:\n\n" + "\n".join(appointments_text)

            return {
                "success": True,
                "message": message,
                "appointments": appointments,
                "count": len(appointments),
            }

        except Exception as e:
            logger.error(f"Error getting appointments: {e}")
            return {
                "success": False,
                "message": "Error retrieving appointments.",
                "appointments": [],
                "error": str(e),
            }
