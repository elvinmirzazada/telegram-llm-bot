# Docker Deployment Guide

## 📋 Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)
- Telegram bot token from [@BotFather](https://t.me/botfather)
- OpenAI API key

## 🚀 Quick Start

### 1. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your actual credentials
nano .env  # or use your preferred editor
```

### 2. Required Environment Variables

**Must configure these before running:**

```bash
# Telegram (Required)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789

# OpenAI (Required)
OPENAI_API_KEY=sk-proj-your_actual_openai_api_key_here

# Database (Update password)
POSTGRES_PASSWORD=your_strong_password_here

# Security (Generate strong key)
SECRET_KEY=$(openssl rand -hex 32)
```

### 3. Build and Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode (background)
docker-compose up -d --build
```

### 4. Verify Services are Running

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f app

# Check health
curl http://localhost:8000/health
```

## 📊 Services Overview

### App Service (FastAPI + Telegram Bot)
- **Port:** 8000
- **Health Check:** http://localhost:8000/health
- **API Docs:** http://localhost:8000/docs (debug mode only)
- **Entrypoint:** uvicorn

### PostgreSQL Database
- **Port:** 5432
- **Database:** telegram_bot
- **Volume:** postgres_data (persistent storage)
- **Health Check:** Built-in pg_isready

## 🔧 Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Volumes (⚠️ Data Loss)
```bash
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs -f

# Only app
docker-compose logs -f app

# Only database
docker-compose logs -f postgres
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build app
```

### Execute Commands in Container
```bash
# Access app container shell
docker-compose exec app bash

# Run migrations (when you create them)
docker-compose exec app python -m alembic upgrade head

# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d telegram_bot
```

### View Container Resource Usage
```bash
docker-compose stats
```

## 🔍 Troubleshooting

### App Won't Start

**Check logs:**
```bash
docker-compose logs app
```

**Common issues:**
- Missing `TELEGRAM_BOT_TOKEN` or `OPENAI_API_KEY`
- Database not ready (wait for health check)
- Port 8000 already in use

**Solution:**
```bash
# Restart services
docker-compose restart

# Force rebuild
docker-compose down
docker-compose up --build
```

### Database Connection Issues

**Check database is healthy:**
```bash
docker-compose ps postgres
```

**Test connection:**
```bash
docker-compose exec postgres pg_isready -U postgres
```

**Reset database:**
```bash
docker-compose down -v
docker-compose up -d postgres
# Wait for health check, then start app
docker-compose up -d app
```

### View Application Health

```bash
# API health
curl http://localhost:8000/health

# Database health (from within app)
docker-compose exec app python -c "
from app.db.session import check_database_connection
import asyncio
print('DB Healthy:', asyncio.run(check_database_connection()))
"
```

## 🌐 Setting Up Telegram Webhook

### Option 1: Using the API Endpoint

```bash
curl -X POST http://localhost:8000/telegram/webhook/set \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook"}'
```

### Option 2: Set in Environment Variables

Edit `.env`:
```bash
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
```

Then restart:
```bash
docker-compose restart app
```

### Check Webhook Status

```bash
curl http://localhost:8000/telegram/webhook/info
```

## 📦 Production Deployment

### 1. Use Docker Secrets (Recommended)

```yaml
# docker-compose.prod.yml
secrets:
  telegram_token:
    file: ./secrets/telegram_token.txt
  openai_key:
    file: ./secrets/openai_key.txt
```

### 2. Use Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Enable HTTPS with Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com
```

### 4. Production Environment Variables

```bash
DEBUG=false
LOG_LEVEL=WARNING
DB_ECHO=false
```

## 🔐 Security Checklist

- [ ] Change default `POSTGRES_PASSWORD`
- [ ] Generate strong `SECRET_KEY`
- [ ] Use `WEBHOOK_SECRET_TOKEN` for webhook security
- [ ] Set `DEBUG=false` in production
- [ ] Use HTTPS for webhook URL
- [ ] Restrict PostgreSQL port (remove from ports in production)
- [ ] Use Docker secrets for sensitive data
- [ ] Regular database backups
- [ ] Monitor logs for suspicious activity

## 💾 Database Backup

### Backup
```bash
docker-compose exec postgres pg_dump -U postgres telegram_bot > backup.sql
```

### Restore
```bash
cat backup.sql | docker-compose exec -T postgres psql -U postgres telegram_bot
```

## 📈 Monitoring

### Health Checks
- App: http://localhost:8000/health
- Bot: http://localhost:8000/telegram/health
- Database: Built into docker-compose

### Logs
```bash
# Follow all logs
docker-compose logs -f

# Search logs
docker-compose logs app | grep ERROR
```

### Metrics
Add to docker-compose.yml for production monitoring:
- Prometheus
- Grafana
- cAdvisor

## 🆘 Support

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Verify environment variables in `.env`
3. Ensure ports 8000 and 5432 are available
4. Check Docker daemon is running
5. Verify bot token with [@BotFather](https://t.me/botfather)

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [aiogram Documentation](https://docs.aiogram.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

