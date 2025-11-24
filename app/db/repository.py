"""
Database Repository Layer

Implements repository pattern for database operations.
Provides abstraction over SQLAlchemy for cleaner business logic.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: AsyncSession instance for database operations
        """
        self.session = session

    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a parametrized SQL query safely.

        Args:
            query: SQL query string
            params: Dictionary of query parameters

        Returns:
            Query result

        Raises:
            DatabaseError: If query execution fails
        """
        try:
            result = await self.session.execute(
                text(query),
                params or {}
            )
            return result
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"Database operation failed: {str(e)}") from e


class AppointmentRepository(BaseRepository):
    """Repository for appointment-related database operations."""

    async def get_available_slots(
        self,
        date: datetime.date,
        duration_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get available appointment slots for a specific date.

        This query finds time slots that don't conflict with existing appointments.
        Assumes business hours are 9:00 AM to 5:00 PM with 30-minute slots.

        Args:
            date: The date to check for availability
            duration_minutes: Duration of appointment slot in minutes

        Returns:
            List of available time slots with slot information

        Example return:
            [
                {'slot_time': '09:00', 'slot_datetime': datetime(...), 'available': True},
                {'slot_time': '09:30', 'slot_datetime': datetime(...), 'available': True},
            ]
        """
        query = """
            WITH RECURSIVE time_slots AS (
                -- Generate time slots from 9:00 to 17:00 (5:00 PM)
                SELECT 
                    :target_date::date + time '09:00' AS slot_time
                UNION ALL
                SELECT 
                    slot_time + interval ':duration minutes'
                FROM time_slots
                WHERE slot_time < :target_date::date + time '17:00' - interval ':duration minutes'
            ),
            booked_slots AS (
                -- Get all booked appointments for the target date
                SELECT 
                    appointment_time::time AS booked_time
                FROM appointments
                WHERE appointment_date = :target_date::date
                    AND status IN ('confirmed', 'pending')
            )
            SELECT 
                ts.slot_time::time AS slot_time,
                ts.slot_time AS slot_datetime,
                CASE 
                    WHEN bs.booked_time IS NULL THEN true
                    ELSE false
                END AS available
            FROM time_slots ts
            LEFT JOIN booked_slots bs 
                ON ts.slot_time::time = bs.booked_time
            WHERE bs.booked_time IS NULL
            ORDER BY ts.slot_time;
        """

        try:
            result = await self.execute_query(
                query,
                {
                    "target_date": date.isoformat(),
                    "duration": duration_minutes
                }
            )
            rows = result.fetchall()

            return [
                {
                    "slot_time": str(row[0]),
                    "slot_datetime": row[1],
                    "available": row[2]
                }
                for row in rows
            ]
        except DatabaseError as e:
            logger.error(f"Failed to get available slots for {date}: {e}")
            raise

    async def create_appointment(
        self,
        customer_id: int,
        date: str,
        time: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new appointment with transaction handling.

        Args:
            customer_id: ID of the customer booking the appointment
            date: Appointment date in ISO format (YYYY-MM-DD)
            time: Appointment time in HH:MM format
            notes: Optional notes for the appointment

        Returns:
            Dictionary containing the created appointment details

        Raises:
            DatabaseError: If appointment creation fails
            ValueError: If date/time format is invalid

        Example:
            appointment = await repo.create_appointment(
                customer_id=123,
                date="2025-11-25",
                time="14:30",
                notes="First consultation"
            )
        """
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
            datetime.datetime.strptime(time, "%H:%M")
        except ValueError as e:
            raise ValueError(f"Invalid date/time format: {e}")

        query = """
            INSERT INTO appointments (
                customer_id,
                appointment_date,
                appointment_time,
                notes,
                status,
                created_at
            )
            VALUES (
                :customer_id,
                :appointment_date::date,
                :appointment_time::time,
                :notes,
                'pending',
                NOW()
            )
            RETURNING 
                id,
                customer_id,
                appointment_date,
                appointment_time,
                notes,
                status,
                created_at;
        """

        try:
            result = await self.execute_query(
                query,
                {
                    "customer_id": customer_id,
                    "appointment_date": date,
                    "appointment_time": time,
                    "notes": notes
                }
            )

            row = result.fetchone()
            if not row:
                raise DatabaseError("Failed to create appointment - no data returned")

            await self.session.commit()

            logger.info(
                f"Created appointment {row[0]} for customer {customer_id} "
                f"on {date} at {time}"
            )

            return {
                "id": row[0],
                "customer_id": row[1],
                "appointment_date": row[2],
                "appointment_time": row[3],
                "notes": row[4],
                "status": row[5],
                "created_at": row[6]
            }

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(f"Failed to create appointment: {e}")
            raise

    async def get_appointment_by_id(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        """
        Get appointment details by ID.

        Args:
            appointment_id: Unique appointment identifier

        Returns:
            Appointment details or None if not found
        """
        query = """
            SELECT 
                id,
                customer_id,
                appointment_date,
                appointment_time,
                notes,
                status,
                created_at,
                updated_at
            FROM appointments
            WHERE id = :appointment_id;
        """

        result = await self.execute_query(query, {"appointment_id": appointment_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "customer_id": row[1],
            "appointment_date": row[2],
            "appointment_time": row[3],
            "notes": row[4],
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7]
        }

    async def get_customer_appointments(
        self,
        customer_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all appointments for a customer.

        Args:
            customer_id: Customer ID
            status: Optional status filter (pending, confirmed, cancelled, completed)

        Returns:
            List of appointment dictionaries
        """
        query = """
            SELECT 
                id,
                customer_id,
                appointment_date,
                appointment_time,
                notes,
                status,
                created_at
            FROM appointments
            WHERE customer_id = :customer_id
        """

        params: Dict[str, Any] = {"customer_id": customer_id}

        if status:
            query += " AND status = :status"
            params["status"] = status

        query += " ORDER BY appointment_date, appointment_time;"

        result = await self.execute_query(query, params)
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "customer_id": row[1],
                "appointment_date": row[2],
                "appointment_time": row[3],
                "notes": row[4],
                "status": row[5],
                "created_at": row[6]
            }
            for row in rows
        ]

    async def update_appointment_status(
        self,
        appointment_id: int,
        status: str
    ) -> bool:
        """
        Update appointment status.

        Args:
            appointment_id: Appointment ID
            status: New status (pending, confirmed, cancelled, completed)

        Returns:
            True if update successful, False otherwise
        """
        query = """
            UPDATE appointments
            SET 
                status = :status,
                updated_at = NOW()
            WHERE id = :appointment_id
            RETURNING id;
        """

        try:
            result = await self.execute_query(
                query,
                {"appointment_id": appointment_id, "status": status}
            )
            row = result.fetchone()
            await self.session.commit()

            success = row is not None
            if success:
                logger.info(f"Updated appointment {appointment_id} status to {status}")
            return success

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(f"Failed to update appointment status: {e}")
            return False


class CustomerRepository(BaseRepository):
    """Repository for customer-related database operations."""

    async def get_customer_by_telegram_id(
        self,
        telegram_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get customer information by Telegram ID.

        Args:
            telegram_id: Telegram user ID (as string)

        Returns:
            Customer details or None if not found

        Example return:
            {
                'id': 123,
                'telegram_id': '987654321',
                'username': 'johndoe',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+1234567890',
                'created_at': datetime(...)
            }
        """
        query = """
            SELECT 
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                phone,
                email,
                created_at,
                updated_at
            FROM telegram_customers
            WHERE telegram_id = :telegram_id;
        """

        try:
            result = await self.execute_query(query, {"telegram_id": telegram_id})
            row = result.fetchone()

            if not row:
                logger.debug(f"No customer found with telegram_id: {telegram_id}")
                return None

            return {
                "id": row[0],
                "telegram_id": row[1],
                "username": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "phone": row[5],
                "email": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }

        except DatabaseError as e:
            logger.error(f"Failed to get customer by telegram_id {telegram_id}: {e}")
            raise

    async def create_customer(
        self,
        telegram_id: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new customer record.

        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: Customer first name
            last_name: Customer last name
            phone: Customer phone number
            email: Customer email address

        Returns:
            Created customer details

        Raises:
            DatabaseError: If customer creation fails
        """
        query = """
            INSERT INTO telegram_customers (
                telegram_id,
                username,
                first_name,
                last_name,
                phone,
                created_at,
                email
            )
            VALUES (
                :telegram_id,
                :username,
                :first_name,
                :last_name,
                :phone,
                NOW(),
                :email
            )
            RETURNING 
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                phone,
                created_at,
                email;
        """

        try:
            result = await self.execute_query(
                query,
                {
                    "telegram_id": telegram_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "email": email
                }
            )

            row = result.fetchone()
            if not row:
                raise DatabaseError("Failed to create customer - no data returned")

            await self.session.commit()

            logger.info(f"Created customer {row[0]} with telegram_id {telegram_id}")

            return {
                "id": row[0],
                "telegram_id": row[1],
                "username": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "phone": row[5],
                "created_at": row[6],
                "email": row[7]
            }

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(f"Failed to create customer: {e}")
            raise

    async def update_customer(
        self,
        customer_id: int,
        **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Update customer information.

        Args:
            customer_id: Customer ID
            **kwargs: Fields to update

        Returns:
            Updated customer details or None if not found
        """
        allowed_fields = {"username", "first_name", "last_name", "phone", "email"}
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_fields:
            logger.warning("No valid fields provided for update")
            return await self.get_customer_by_id(customer_id)

        set_clause = ", ".join([f"{field} = :{field}" for field in update_fields.keys()])
        query = f"""
            UPDATE customers
            SET 
                {set_clause},
                updated_at = NOW()
            WHERE id = :customer_id
            RETURNING 
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                phone,
                email,
                updated_at;
        """

        params = {**update_fields, "customer_id": customer_id}

        try:
            result = await self.execute_query(query, params)
            row = result.fetchone()

            if row:
                await self.session.commit()
                logger.info(f"Updated customer {customer_id}")

                return {
                    "id": row[0],
                    "telegram_id": row[1],
                    "username": row[2],
                    "first_name": row[3],
                    "last_name": row[4],
                    "phone": row[5],
                    "email": row[6],
                    "updated_at": row[7]
                }
            return None

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(f"Failed to update customer: {e}")
            raise

    async def get_customer_by_id(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get customer by ID.

        Args:
            customer_id: Customer ID

        Returns:
            Customer details or None if not found
        """
        query = """
            SELECT 
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                phone,
                email,
                created_at,
                updated_at
            FROM customers
            WHERE id = :customer_id;
        """

        result = await self.execute_query(query, {"customer_id": customer_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "telegram_id": row[1],
            "username": row[2],
            "first_name": row[3],
            "last_name": row[4],
            "phone": row[5],
            "email": row[6],
            "created_at": row[7],
            "updated_at": row[8]
        }


class ConversationRepository(BaseRepository):
    """Repository for conversation history tracking."""

    async def save_message(
        self,
        customer_id: int,
        message_text: str,
        message_type: str = "user",
        context_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save a conversation message.

        Args:
            customer_id: Customer ID
            message_text: Message content
            message_type: Type of message (user/bot)
            context_data: Optional context metadata as JSON

        Returns:
            Created message ID
        """
        query = """
            INSERT INTO conversation_history (
                customer_id,
                message_text,
                message_type,
                context_data,
                created_at
            )
            VALUES (
                :customer_id,
                :message_text,
                :message_type,
                CAST(:context_data AS jsonb),
                NOW()
            )
            RETURNING id;
        """

        import json

        result = await self.execute_query(
            query,
            {
                "customer_id": customer_id,
                "message_text": message_text,
                "message_type": message_type,
                "context_data": json.dumps(context_data) if context_data else None
            }
        )

        row = result.fetchone()
        await self.session.commit()

        return row[0] if row else 0

    async def get_recent_conversation(
        self,
        customer_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation history.

        Args:
            customer_id: Customer ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation messages
        """
        query = """
            SELECT 
                id,
                customer_id,
                message_text,
                message_type,
                context_data,
                created_at
            FROM conversation_history
            WHERE customer_id = :customer_id
            ORDER BY created_at DESC
            LIMIT :limit;
        """

        result = await self.execute_query(
            query,
            {"customer_id": customer_id, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "customer_id": row[1],
                "message_text": row[2],
                "message_type": row[3],
                "context_data": row[4],
                "created_at": row[5]
            }
            for row in reversed(rows)  # Reverse to get chronological order
        ]
