# Development Setup with Live Code Reload

This guide explains how to run the Telegram bot in development mode with live code reload using Docker Compose.

## Quick Start

### 1. Start Development Environment

```bash
# Build and start with live reload
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or in detached mode
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### 2. Watch Logs

```bash
# Follow all logs
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Follow only bot logs
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f bot
```

### 3. Make Changes

Edit any `.py` file in the `app/` directory and the changes will be automatically reloaded without restarting the container!

Example:
```bash
# Edit a file
vim app/bot/handlers.py

# Changes are automatically detected and reloaded
# Check logs to see: "Detected file change in '...'. Reloading..."
```

### 4. Stop Development Environment

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

## Features

### ✅ Live Code Reload
- Changes to `.py` files in `app/` are automatically detected
- Uvicorn reloads the application without container restart
- Much faster development workflow

### ✅ Debug Mode Enabled
- API documentation available at `http://localhost:8088/docs`
- Detailed error messages
- CORS enabled for frontend development

### ✅ Exposed Ports
- **8088**: FastAPI application
- **11434**: Ollama API (for debugging/testing)
- **5432**: PostgreSQL database

### ✅ Volume Mounts
- `./app` → `/app/app` (read-write)
- `./pyproject.toml` → `/app/pyproject.toml` (read-only)
- `./requirements.txt` → `/app/requirements.txt` (read-only)

## Tips

### Faster Builds

The development Dockerfile skips pre-pulling the Ollama model. If you want to include it, uncomment these lines in `Dockerfile.dev`:

```dockerfile
RUN ollama serve & \
    sleep 5 && \
    ollama pull phi3 && \
    pkill ollama
```

### Testing Ollama Locally

Since Ollama is exposed on port 11434, you can test it directly:

```bash
# Test Ollama API
curl http://localhost:11434/api/generate -d '{
  "model": "phi3",
  "prompt": "Hello, how are you?",
  "stream": false
}'
```

### Debugging

Access the running container:

```bash
# Get a shell in the bot container
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml exec bot bash

# Check running processes
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml exec bot ps aux

# Check Ollama status
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml exec bot ollama list
```

### Installing New Dependencies

If you add a new package to `requirements.txt` or `pyproject.toml`, rebuild:

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Production vs Development

| Feature | Production | Development |
|---------|-----------|-------------|
| Code location | Copied into image | Mounted as volume |
| Reload on change | No | Yes (automatic) |
| Debug mode | Disabled | Enabled |
| API docs | Disabled | Enabled at `/docs` |
| Ollama exposed | No | Yes (port 11434) |
| Build time | Slower (includes model) | Faster (no model) |

## Aliases (Optional)

Add these to your `~/.bashrc` or `~/.zshrc` for convenience:

```bash
# Development shortcuts
alias dc-dev='sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml'
alias dc-dev-up='dc-dev up -d'
alias dc-dev-down='dc-dev down'
alias dc-dev-logs='dc-dev logs -f'
alias dc-dev-restart='dc-dev restart bot'
```

Then use:
```bash
dc-dev up -d       # Start dev environment
dc-dev-logs bot    # Watch bot logs
dc-dev-restart     # Restart bot service
dc-dev-down        # Stop everything
```

## Troubleshooting

### Changes not reloading?

1. Check uvicorn is running with `--reload`:
   ```bash
   sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml logs bot | grep reload
   ```

2. Ensure the file is in `app/` directory

3. Check file permissions (should be readable by the container)

### Permission Issues?

If you get permission errors with mounted volumes:

```bash
# Fix permissions
sudo chown -R $USER:$USER app/
```

### Port Already in Use?

Stop any existing containers:
```bash
sudo docker compose down
sudo docker ps -a  # Check for orphaned containers
```
version: '3.8'

# Development override for docker-compose.yml
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up

services:
  postgres:
    # Use the same postgres service from docker-compose.yml
    ports:
      - "5432:5432"

  bot:
    # Override the bot service for development
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      # Mount local code for live reload
      - ./app:/app/app:rw
      - ./pyproject.toml:/app/pyproject.toml:ro
      - ./requirements.txt:/app/requirements.txt:ro
      # Exclude pycache to avoid permission issues
      - /app/app/__pycache__
    environment:
      # Enable debug mode
      - DEBUG=true
      - PYTHONUNBUFFERED=1
    command: >
      bash -c "
        ollama serve &
        sleep 5 &&
        uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload --reload-dir /app/app
      "
    ports:
      - "8088:8088"
      - "11434:11434"  # Expose Ollama API for debugging

