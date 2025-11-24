-- Database Schema for Telegram LLM Bot
-- Created: 2025-11-24
-- This script creates all necessary tables for the application

-- Drop tables if they exist (cascade to handle foreign keys)
DROP TABLE IF EXISTS conversation_history CASCADE;
DROP TABLE IF EXISTS telegram_customers CASCADE;

-- Create telegram_customers table
CREATE TABLE telegram_customers (
    id SERIAL PRIMARY KEY,
    telegram_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on telegram_id for fast lookups
CREATE INDEX idx_telegram_customers_telegram_id ON telegram_customers(telegram_id);

-- Create conversation_history table
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'user',
    context_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_conversation_customer
        FOREIGN KEY(customer_id)
        REFERENCES telegram_customers(id)
        ON DELETE CASCADE
);

-- Create indexes for conversation_history
CREATE INDEX idx_conversation_history_customer_id ON conversation_history(customer_id);
CREATE INDEX idx_conversation_history_created_at ON conversation_history(created_at);
CREATE INDEX idx_conversation_history_message_type ON conversation_history(message_type);

-- Add constraint to ensure valid message type
ALTER TABLE conversation_history ADD CONSTRAINT chk_message_type
    CHECK (message_type IN ('user', 'bot'));

-- Create a function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $function$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$ LANGUAGE plpgsql;

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_telegram_customers_updated_at
    BEFORE UPDATE ON telegram_customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Optional: Insert some sample data for testing
-- Uncomment the following lines if you want sample data

-- INSERT INTO telegram_customers (telegram_id, username, first_name, last_name, phone, email)
-- VALUES
--     ('123456789', 'john_doe', 'John', 'Doe', '+1234567890', 'john.doe@example.com'),
--     ('987654321', 'jane_smith', 'Jane', 'Smith', '+0987654321', 'jane.smith@example.com');

-- INSERT INTO conversation_history (customer_id, message_text, message_type, context_data)
-- VALUES
--     (1, 'Hello, I need help with booking', 'user', '{"intent": "greeting"}'),
--     (1, 'Hi! I''d be happy to help you. What can I assist you with?', 'bot', '{"action": "greeting_response"}');

-- Display success message
DO $$
BEGIN
    RAISE NOTICE 'Database tables created successfully!';
    RAISE NOTICE 'Tables created: telegram_customers, conversation_history';
END $$;
