# Telegram LLM Appointment Bot

An intelligent Telegram chatbot powered by Large Language Models (LLM) for natural language appointment booking, scheduling, and management.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![aiogram](https://img.shields.io/badge/aiogram-3.3+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 📖 Description

This project provides a production-ready Telegram bot that uses Large Language Models (OpenAI GPT-4 or compatible APIs) to understand natural language and manage appointments through conversational interactions. Users can book, check availability, reschedule, and cancel appointments simply by chatting with the bot in natural language.

### Key Technologies

- **Backend**: FastAPI (async Python web framework)
- **Bot Framework**: aiogram 3.x (async Telegram bot library)
- **Database**: PostgreSQL with async SQLAlchemy 2.0
- **LLM Integration**: OpenAI API (easily adaptable to other LLMs)
- **Package Manager**: uv (fast Python package installer)
- **Containerization**: Docker & Docker Compose

## ✨ Features

### 🤖 Intelligent Conversation
- Natural language understanding powered by LLM
- Context-aware multi-turn conversations
- Intent detection (book, check availability, reschedule, cancel, smalltalk)
- Entity extraction (date, time, appointment details)
- Conversation history tracking

### 📅 Appointment Management
- **Book appointments** - "I want to book for tomorrow at 2pm"
- **Check availability** - "What times are available on Friday?"
- **Reschedule appointments** - "Move my Monday appointment to Tuesday"
- **Cancel appointments** - "Cancel my appointment on the 25th"
- **View appointments** - List all upcoming appointments

### 🔧 Technical Features
- Async/await throughout for high performance
- Connection pooling for database efficiency
- Parametrized SQL queries for security
- Repository pattern for clean architecture
- Comprehensive error handling
- Health check endpoints
- Docker-ready with multi-stage builds
- Production-optimized with non-root user

### 🛡️ Security
- Webhook secret token validation
- SQL injection prevention
- Environment-based configuration
- Non-root Docker containers
- CORS configuration

## 🚀 Setup

### Prerequisites

- Python 3.12 or higher
- PostgreSQL 14+ (or use Docker)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key (or compatible LLM API)

### 1. Install uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version
```

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/telegram-llm-bot.git
cd telegram-llm-bot
```

### 3. Create Virtual Environment

```bash
# Create virtual environment
uv venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 4. Install Dependencies

```bash
# Install production dependencies
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[dev]"
```

### 5. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

**Required environment variables:**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/telegram_bot

# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789

# OpenAI / LLM
OPENAI_API_KEY=sk-proj-your_actual_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true
LOG_LEVEL=INFO

# Security
SECRET_KEY=$(openssl rand -hex 32)  # Generate a strong secret key
```

### 6. Set Up Database

#### Option A: Using Docker for PostgreSQL Only

```bash
# Start PostgreSQL container
docker run -d \
  --name telegram_bot_postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=telegram_bot \
  -p 5432:5432 \
  postgres:16-alpine
```

#### Option B: Local PostgreSQL Installation

```bash
# Create database
createdb telegram_bot

# Or using psql
psql -U postgres -c "CREATE DATABASE telegram_bot;"
```

**Note:** The application expects existing tables. Create your database schema before running:

```sql
-- Example schema (customize based on your needs)
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

CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    message_text TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    context_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🏃 Running Locally (Without Docker)

### Start the Application

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Run with uvicorn (development mode with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or run directly
python -m app.main
```

### Verify It's Running

```bash
# Check health endpoint
curl http://localhost:8000/health

# View API documentation (if DEBUG=true)
open http://localhost:8000/docs

# Check bot status
curl http://localhost:8000/telegram/health
```

### Set Telegram Webhook (Local Development)

For local development, you need to expose your local server to the internet. Use a tunneling service like [ngrok](https://ngrok.com/):

```bash
# Install ngrok
# Download from https://ngrok.com/download

# Start tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

Then set the webhook:

```bash
# Option 1: Using the API endpoint
curl -X POST http://localhost:8000/telegram/webhook/set \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-ngrok-url.ngrok.io/telegram/webhook"}'

# Option 2: Set in .env and restart
echo "TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok.io/telegram/webhook" >> .env
```

## 🐳 Running with Docker & Docker Compose

### Quick Start

```bash
# Build and start all services
docker-compose up --build

# Or run in background (detached mode)
docker-compose up -d --build
```

### What This Does

1. Builds the FastAPI application with uv
2. Starts PostgreSQL database with persistent volume
3. Starts the bot application
4. Automatically sets up database connection
5. Initializes Telegram webhook (if configured)

### Useful Docker Commands

```bash
# View logs
docker-compose logs -f app

# Check service status
docker-compose ps

# Stop services
docker-compose down

# Stop and remove volumes (⚠️ destroys data)
docker-compose down -v

# Restart after code changes
docker-compose up -d --build app

# Access database
docker-compose exec postgres psql -U postgres -d telegram_bot

# Execute command in app container
docker-compose exec app python -m pytest
```

### Environment Variables for Docker

Edit `.env` file before starting:

```bash
# Database (automatically configured in docker-compose)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=telegram_bot

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook

# LLM
OPENAI_API_KEY=your_openai_key
```

## 🌐 Setting Telegram Webhook

### Get Your Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Set Webhook URL

#### Method 1: Using API Endpoint

```bash
curl -X POST http://your-domain.com/telegram/webhook/set \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook"}'
```

#### Method 2: Environment Variable

Add to `.env`:
```bash
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
WEBHOOK_SECRET_TOKEN=your_secret_token_min_20_chars  # Optional but recommended
```

Restart the application - webhook will be set automatically on startup.

#### Method 3: Direct Telegram API Call

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook"}'
```

### Verify Webhook

```bash
# Check webhook status
curl http://your-domain.com/telegram/webhook/info

# Or via Telegram API
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

### Important Notes

- Webhook URL **must be HTTPS** (except for localhost)
- Must be publicly accessible (not behind firewall)
- Telegram will send POST requests to this URL
- Use ngrok for local development testing

## 🔑 Configuring LLM API Keys

### OpenAI (Default)

1. Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `.env`:

```bash
OPENAI_API_KEY=sk-proj-your_actual_key_here
OPENAI_MODEL=gpt-4-turbo-preview  # or gpt-3.5-turbo for cheaper option
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=500
```

### Using Other LLM Providers

The application is designed to work with any OpenAI-compatible API. Modify `app/services/llm.py`:

#### Anthropic Claude

```python
# In app/services/llm.py, uncomment and configure:
import anthropic

client = anthropic.AsyncAnthropic(api_key=self.api_key)

response = await client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=self.max_tokens,
    temperature=self.temperature,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}]
)
```

Then in `.env`:
```bash
OPENAI_API_KEY=your_anthropic_key  # Reuses same env var
OPENAI_MODEL=claude-3-opus-20240229
```

#### Local LLMs (Ollama, LM Studio)

```bash
# Point to local API endpoint
OPENAI_API_KEY=not-needed-for-local
OPENAI_MODEL=llama2
# Configure base_url in llm.py to point to http://localhost:11434
```

### Cost Optimization

```bash
# Use cheaper models for development
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=300

# Production settings
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_TEMPERATURE=0.7  # Lower = more deterministic, higher = more creative
```

## 🚀 Production Deployment with NGINX

### Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Domain name pointing to your server
- SSL certificate (Let's Encrypt recommended)

### Step 1: Install Dependencies on Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose-plugin

# Install NGINX
sudo apt install nginx

# Install Certbot for SSL
sudo apt install certbot python3-certbot-nginx
```

### Step 2: Clone and Configure Application

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/yourusername/telegram-llm-bot.git
cd telegram-llm-bot

# Create production .env
sudo cp .env.example .env
sudo nano .env
```

**Production `.env` configuration:**

```bash
# Database
POSTGRES_PASSWORD=strong_random_password_here

# Telegram
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
WEBHOOK_SECRET_TOKEN=$(openssl rand -hex 32)

# LLM
OPENAI_API_KEY=your_actual_openai_key

# Application - Production Settings
DEBUG=false
LOG_LEVEL=WARNING
SECRET_KEY=$(openssl rand -hex 32)
```

### Step 3: Configure NGINX Reverse Proxy

```bash
# Create NGINX configuration
sudo nano /etc/nginx/sites-available/telegram-bot
```

**NGINX Configuration:**

```nginx
# /etc/nginx/sites-available/telegram-bot

upstream telegram_bot {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration (certbot will add these)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/telegram_bot_access.log;
    error_log /var/log/nginx/telegram_bot_error.log;

    # Max body size
    client_max_body_size 10M;

    # Proxy settings
    location / {
        proxy_pass http://telegram_bot;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (optional - expose publicly)
    location /health {
        proxy_pass http://telegram_bot/health;
        access_log off;
    }
}
```

**Enable the configuration:**

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload NGINX
sudo systemctl reload nginx
```

### Step 4: Obtain SSL Certificate

```bash
# Get SSL certificate from Let's Encrypt
sudo certbot --nginx -d your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

Certbot will automatically update your NGINX configuration with SSL settings.

### Step 5: Start Application with Docker

```bash
# Navigate to application directory
cd /opt/telegram-llm-bot

# Start services
sudo docker-compose up -d --build

# Check status
sudo docker-compose ps

# View logs
sudo docker-compose logs -f app
```

### Step 6: Configure Firewall

```bash
# Allow HTTP, HTTPS, and SSH
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# PostgreSQL port should NOT be exposed externally
# Only accessible within Docker network
```

### Step 7: Set Telegram Webhook

```bash
# Set webhook to your domain
curl -X POST https://your-domain.com/telegram/webhook/set \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook"}'

# Verify webhook
curl https://your-domain.com/telegram/webhook/info
```

### Step 8: Configure Application as System Service (Optional)

Create systemd service for auto-start on boot:

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

```ini
[Unit]
Description=Telegram LLM Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/telegram-llm-bot
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

### Production Monitoring

#### Check Application Health

```bash
# Via web
curl https://your-domain.com/health

# Check bot specifically
curl https://your-domain.com/telegram/health

# View logs
sudo docker-compose logs -f app
```

#### Monitor Resources

```bash
# Docker container stats
sudo docker stats

# System resources
htop
```

#### Database Backup

```bash
# Create backup
sudo docker-compose exec postgres pg_dump -U postgres telegram_bot > backup_$(date +%Y%m%d).sql

# Restore backup
cat backup_20251123.sql | sudo docker-compose exec -T postgres psql -U postgres telegram_bot
```

### Security Best Practices

1. **Use strong passwords** for database and secrets
2. **Keep secrets out of version control** (use `.env` files)
3. **Regular updates**: `sudo apt update && sudo apt upgrade`
4. **Monitor logs** for suspicious activity
5. **Backup database** regularly
6. **Use webhook secret token** for validation
7. **Limit API rate** in NGINX if needed
8. **Enable firewall** (ufw) and only open necessary ports
9. **Set up monitoring** (Prometheus/Grafana recommended)
10. **Regular security audits**

## 📚 Development

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_config.py -v
```

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

### Project Structure

```
telegram-llm-bot/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── bot/
│   │   ├── handlers.py      # Telegram message handlers
│   │   └── webhook.py       # Webhook setup and routes
│   ├── db/
│   │   ├── session.py       # Database session management
│   │   └── repository.py    # Database repositories
│   ├── services/
│   │   ├── llm.py           # LLM service integration
│   │   └── appointment.py   # Appointment business logic
│   └── models/
│       └── schemas.py       # Pydantic schemas
├── tests/                   # Test suite
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose orchestration
├── pyproject.toml          # Project dependencies
└── README.md               # This file
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Bot Not Responding

1. **Check webhook is set**: `curl https://your-domain.com/telegram/webhook/info`
2. **Verify bot token**: Test with BotFather
3. **Check logs**: `docker-compose logs -f app`
4. **Verify webhook URL is HTTPS** and publicly accessible

### Database Connection Issues

```bash
# Check database is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres pg_isready -U postgres

# Check logs
docker-compose logs postgres
```

### LLM API Errors

1. **Verify API key** is correct and has credits
2. **Check model name** is valid for your API
3. **Monitor rate limits** - add delays if needed
4. **Check logs** for specific error messages

### NGINX 502 Bad Gateway

1. **Ensure app is running**: `docker-compose ps`
2. **Check app logs**: `docker-compose logs app`
3. **Verify port 8000** is not blocked
4. **Test direct connection**: `curl http://localhost:8000/health`

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/telegram-llm-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/telegram-llm-bot/discussions)
- **Email**: your-email@example.com

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [aiogram](https://aiogram.dev/) - Telegram Bot framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [uv](https://github.com/astral-sh/uv) - Fast package installer
- [OpenAI](https://openai.com/) - LLM API

---

**Built with ❤️ using Python, FastAPI, and aiogram**

For more information, see [DOCKER_GUIDE.md](DOCKER_GUIDE.md) and [DATABASE.md](DATABASE.md).
