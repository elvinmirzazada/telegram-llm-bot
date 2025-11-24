# Database Layer Documentation

## Overview

This document describes the production-ready database layer implementation for the Telegram LLM Bot application.

## Architecture

The database layer follows the **Repository Pattern** and uses:
- **SQLAlchemy 2.0** with async support
- **asyncpg** driver for PostgreSQL
- **Dependency Injection** for FastAPI integration
- **Parametrized SQL queries** for security

## Components

### 1. Configuration (`app/config.py`)

Manages all application settings using `pydantic-settings`:

```python
from app.config import settings

# Access configuration
print(settings.database_url_str)
print(settings.db_pool_size)
```

**Features:**
- Automatic `.env` file loading
- Type validation with Pydantic
- Automatic conversion of `postgresql://` to `postgresql+asyncpg://`
- Cached singleton pattern via `@lru_cache()`

**Key Settings:**
- `database_url`: PostgreSQL connection URL
- `db_pool_size`: Connection pool size (default: 10)
- `db_max_overflow`: Max overflow connections (default: 20)
- `db_pool_timeout`: Connection timeout in seconds (default: 30)
- `db_pool_recycle`: Connection recycle time (default: 3600s)

### 2. Session Management (`app/db/session.py`)

Handles async database sessions with proper lifecycle management.

#### FastAPI Dependency Injection

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session

@app.get("/appointments")
async def get_appointments(db: AsyncSession = Depends(get_db_session)):
    # Use db session here
    result = await db.execute(text("SELECT * FROM appointments"))
    return result.fetchall()
```

#### Context Manager (for background tasks)

```python
from app.db.session import get_db_context

async def background_task():
    async with get_db_context() as db:
        result = await db.execute(text("SELECT 1"))
        # Transaction automatically committed
```

#### Health Check

```python
from app.db.session import check_database_connection

is_healthy = await check_database_connection()
```

#### Application Lifecycle

```python
from app.db.session import close_database_connection

# On application shutdown
await close_database_connection()
```

**Features:**
- Automatic commit on success
- Automatic rollback on error
- Connection pooling with health checks
- Proper resource cleanup

### 3. Repository Layer (`app/db/repository.py`)

Implements data access logic with three main repositories.

#### AppointmentRepository

**Methods:**

1. **`get_available_slots(date, duration_minutes=30)`**
   ```python
   slots = await appointment_repo.get_available_slots(
       date=datetime.date(2025, 11, 25),
       duration_minutes=30
   )
   # Returns: [{'slot_time': '09:00', 'slot_datetime': ..., 'available': True}, ...]
   ```

2. **`create_appointment(customer_id, date, time, notes=None)`**
   ```python
   appointment = await appointment_repo.create_appointment(
       customer_id=123,
       date="2025-11-25",
       time="14:30",
       notes="First consultation"
   )
   # Returns: {'id': 1, 'customer_id': 123, 'status': 'pending', ...}
   ```

3. **`get_appointment_by_id(appointment_id)`**
   ```python
   appointment = await appointment_repo.get_appointment_by_id(1)
   ```

4. **`get_customer_appointments(customer_id, status=None)`**
   ```python
   appointments = await appointment_repo.get_customer_appointments(
       customer_id=123,
       status="pending"  # Optional filter
   )
   ```

5. **`update_appointment_status(appointment_id, status)`**
   ```python
   success = await appointment_repo.update_appointment_status(1, "confirmed")
   ```

#### CustomerRepository

**Methods:**

1. **`get_customer_by_telegram_id(telegram_id)`**
   ```python
   customer = await customer_repo.get_customer_by_telegram_id("987654321")
   # Returns: {'id': 123, 'telegram_id': '987654321', 'username': 'johndoe', ...}
   ```

2. **`create_customer(telegram_id, username=None, first_name=None, ...)`**
   ```python
   customer = await customer_repo.create_customer(
       telegram_id="987654321",
       username="johndoe",
       first_name="John",
       last_name="Doe",
       phone="+1234567890"
   )
   ```

3. **`update_customer(customer_id, **kwargs)`**
   ```python
   customer = await customer_repo.update_customer(
       123,
       phone="+9876543210",
       email="newemail@example.com"
   )
   ```

4. **`get_customer_by_id(customer_id)`**
   ```python
   customer = await customer_repo.get_customer_by_id(123)
   ```

#### ConversationRepository

**Methods:**

1. **`save_message(customer_id, message_text, message_type='user', context_data=None)`**
   ```python
   message_id = await conversation_repo.save_message(
       customer_id=123,
       message_text="I want to book an appointment",
       message_type="user",
       context_data={"intent": "book_appointment", "confidence": 0.95}
   )
   ```

2. **`get_recent_conversation(customer_id, limit=10)`**
   ```python
   messages = await conversation_repo.get_recent_conversation(123, limit=10)
   ```

## Usage Example

### Complete Flow

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.db.repository import AppointmentRepository, CustomerRepository

@app.post("/book-appointment")
async def book_appointment(
    telegram_id: str,
    date: str,
    time: str,
    db: AsyncSession = Depends(get_db_session)
):
    # Initialize repositories
    customer_repo = CustomerRepository(db)
    appointment_repo = AppointmentRepository(db)
    
    # Get or create customer
    customer = await customer_repo.get_customer_by_telegram_id(telegram_id)
    if not customer:
        customer = await customer_repo.create_customer(telegram_id=telegram_id)
    
    # Check availability
    import datetime
    appointment_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    slots = await appointment_repo.get_available_slots(appointment_date)
    
    if not any(slot["slot_time"] == time and slot["available"] for slot in slots):
        return {"error": "Time slot not available"}
    
    # Create appointment
    appointment = await appointment_repo.create_appointment(
        customer_id=customer["id"],
        date=date,
        time=time,
        notes="Booked via Telegram bot"
    )
    
    return {"success": True, "appointment": appointment}
```

## Database Schema Assumptions

The code assumes the following tables exist:

### `customers` table
```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    telegram_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### `appointments` table
```sql
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### `conversation_history` table
```sql
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    message_text TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    context_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Features

1. **Parametrized Queries**: All SQL uses named parameters to prevent SQL injection
2. **Type Validation**: Pydantic validates all configuration values
3. **Connection Pooling**: Prevents connection exhaustion attacks
4. **Transaction Management**: Automatic rollback on errors
5. **Field Whitelisting**: Only allowed fields can be updated

## Error Handling

```python
from app.db.repository import DatabaseError

try:
    appointment = await appointment_repo.create_appointment(...)
except DatabaseError as e:
    logger.error(f"Database operation failed: {e}")
    return {"error": "Failed to create appointment"}
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    return {"error": "Invalid date/time format"}
```

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_repository.py

# Run with verbose output
pytest -v
```

## Performance Considerations

1. **Connection Pooling**: Pre-configured pool prevents connection overhead
2. **Pool Pre-ping**: Validates connections before use
3. **Expire on Commit**: Disabled to reduce database round-trips
4. **Async Operations**: Non-blocking I/O for high concurrency
5. **Connection Recycling**: Prevents stale connections

## Best Practices

1. **Always use dependency injection** in FastAPI routes
2. **Use context manager** for background tasks
3. **Handle DatabaseError** exceptions appropriately
4. **Validate input** before passing to repository methods
5. **Log errors** for debugging and monitoring
6. **Close connections** on application shutdown

## Monitoring

Check database health:
```python
from app.db.session import check_database_connection

if not await check_database_connection():
    # Alert monitoring system
    logger.critical("Database connection failed!")
```

