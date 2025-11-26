# Ollama Docker Setup Guide

This guide provides complete instructions for setting up and using Ollama (local LLM) with your Telegram bot in Docker.

## Quick Start

### 1. Start Ollama Service

```bash
# Start just the Ollama service
docker-compose up -d ollama

# Or start all services
docker-compose up -d
```

### 2. Wait for Ollama to be Ready

```bash
# Check if Ollama is running
docker ps | grep ollama

# Check Ollama health
docker exec telegram_bot_ollama curl http://localhost:11434/api/tags
```

### 3. Create/Pull the Model

#### Option A: Use the automated setup script
```bash
# Run the full setup (starts Ollama + creates model)
./setup-ollama.sh setup

# Or use interactive menu
./setup-ollama.sh
```

#### Option B: Manual setup
```bash
# Pull a base model (e.g., llama2, mistral, gemma)
docker exec telegram_bot_ollama ollama pull llama2

# Create custom appointment-bot model
docker exec telegram_bot_ollama ollama create appointment-bot -f /path/to/Modelfile

# Or copy and use an existing model
docker exec telegram_bot_ollama ollama copy llama2 appointment-bot
```

## Complete Command Reference

### Starting Services

```bash
# Start only Ollama
docker-compose up -d ollama

# Start all services (Postgres + Ollama + App)
docker-compose up -d

# Start with logs
docker-compose up ollama
```

### Managing Ollama Container

```bash
# Check status
docker ps | grep ollama

# View logs
docker logs telegram_bot_ollama
docker logs -f telegram_bot_ollama  # Follow logs

# Restart Ollama
docker-compose restart ollama

# Stop Ollama
docker-compose stop ollama

# Remove Ollama (keeps data)
docker-compose stop ollama && docker-compose rm ollama

# Full reset (removes data too)
docker-compose down -v
docker volume rm telegram-llm-bot_ollama_data
```

### Working with Models

#### List Available Models
```bash
docker exec telegram_bot_ollama ollama list
```

#### Pull a Model from Registry
```bash
# Pull popular models
docker exec telegram_bot_ollama ollama pull llama2
docker exec telegram_bot_ollama ollama pull llama2:13b
docker exec telegram_bot_ollama ollama pull mistral
docker exec telegram_bot_ollama ollama pull gemma
docker exec telegram_bot_ollama ollama pull phi
```

#### Create Custom Model

First, create a Modelfile:

```dockerfile
# Modelfile
FROM llama2

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40

SYSTEM """You are an intelligent appointment booking assistant. Your role is to help users book, check, reschedule, or cancel appointments through natural conversation.

You must ALWAYS respond with valid JSON in this format:
{
    "intent": "book_appointment|check_availability|reschedule_appointment|cancel_appointment|smalltalk",
    "confidence": 0.0-1.0,
    "entities": {
        "date": "YYYY-MM-DD or null",
        "time": "HH:MM or null",
        "service_type": "string or null",
        "appointment_id": "integer or null"
    },
    "missing_info": ["list of missing fields"],
    "user_message": "natural language response to user",
    "action": "proceed|ask_clarification|provide_info",
    "metadata": {}
}

Be helpful, professional, and always extract intent and entities from user messages."""
```

Then create the model:

```bash
# Copy Modelfile into container
docker cp Modelfile telegram_bot_ollama:/tmp/Modelfile

# Create the model
docker exec telegram_bot_ollama ollama create appointment-bot -f /tmp/Modelfile

# Verify it was created
docker exec telegram_bot_ollama ollama list
```

#### Test a Model
```bash
# Interactive test
docker exec -it telegram_bot_ollama ollama run appointment-bot

# Single prompt test
docker exec telegram_bot_ollama ollama run appointment-bot "I want to book an appointment tomorrow at 2pm"

# Test via API
docker exec telegram_bot_ollama curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "appointment-bot", "prompt": "I need to schedule a meeting", "stream": false}'
```

#### Delete a Model
```bash
docker exec telegram_bot_ollama ollama rm appointment-bot
```

#### Copy/Rename a Model
```bash
docker exec telegram_bot_ollama ollama copy llama2 appointment-bot
```

### Accessing Ollama API

#### From Host Machine
```bash
# Test API endpoint
curl http://localhost:11434/api/tags

# Generate response
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "appointment-bot",
    "prompt": "I want to book an appointment",
    "stream": false
  }'
```

#### From App Container
```bash
# The app can access Ollama at: http://ollama:11434
# This is already configured in docker-compose.yml as OLLAMA_HOST

# Test from app container
docker exec telegram_bot_app curl http://ollama:11434/api/tags
```

### Environment Variables

Add these to your `.env` file:

```bash
# Local LLM Configuration (Ollama)
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=appointment-bot
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=500
USE_LOCAL_LLM=true
```

## GPU Support (Optional)

If you have an NVIDIA GPU, the docker-compose.yml already includes GPU support.

### Requirements:
1. NVIDIA GPU
2. NVIDIA Docker Runtime installed

### Install NVIDIA Docker Runtime:
```bash
# Add NVIDIA Docker repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker
sudo systemctl restart docker

# Test GPU
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Without GPU:
If you don't have a GPU, comment out the deploy section in docker-compose.yml:

```yaml
ollama:
  image: ollama/ollama:latest
  # ... other config ...
  # deploy:
  #   resources:
  #     reservations:
  #       devices:
  #         - driver: nvidia
  #           count: all
  #           capabilities: [gpu]
```

## Troubleshooting

### Ollama Container Won't Start
```bash
# Check logs
docker logs telegram_bot_ollama

# Check if port is already in use
sudo lsof -i :11434
netstat -tulpn | grep 11434

# Remove and recreate
docker-compose down
docker-compose up -d ollama
```

### Model Not Found
```bash
# List available models
docker exec telegram_bot_ollama ollama list

# Pull the model first
docker exec telegram_bot_ollama ollama pull llama2

# Create your custom model
docker exec telegram_bot_ollama ollama create appointment-bot -f /tmp/Modelfile
```

### API Not Responding
```bash
# Check if Ollama process is running
docker exec telegram_bot_ollama ps aux | grep ollama

# Test API endpoint
docker exec telegram_bot_ollama curl http://localhost:11434/api/tags

# Restart the service
docker-compose restart ollama
```

### Out of Memory
```bash
# Check container resources
docker stats telegram_bot_ollama

# Use a smaller model
docker exec telegram_bot_ollama ollama pull llama2:7b
# Instead of llama2:13b or llama2:70b

# Increase Docker memory limit in Docker Desktop settings
```

### Slow Response Times
- Use a smaller model (7B instead of 13B)
- Enable GPU support if available
- Increase container memory allocation
- Use quantized models (they're faster but slightly less accurate)

## Complete Setup Example

Here's a complete workflow from scratch:

```bash
# 1. Start services
docker-compose up -d

# 2. Wait for Ollama to be ready
sleep 10

# 3. Check status
docker ps | grep ollama

# 4. Pull base model
docker exec telegram_bot_ollama ollama pull llama2

# 5. Create custom model using the automated script
./setup-ollama.sh create

# 6. Test the model
docker exec telegram_bot_ollama ollama run appointment-bot "Hello, I need help"

# 7. Update .env file to use local LLM
echo "USE_LOCAL_LLM=true" >> .env

# 8. Restart app to use local LLM
docker-compose restart app

# 9. Check app logs
docker logs -f telegram_bot_app
```

## Using the Setup Script

The `setup-ollama.sh` script provides an easy way to manage Ollama:

```bash
# Interactive menu
./setup-ollama.sh

# Quick setup (start + create model)
./setup-ollama.sh setup

# Start Ollama
./setup-ollama.sh start

# Create custom model
./setup-ollama.sh create

# List models
./setup-ollama.sh list

# Test model
./setup-ollama.sh test appointment-bot

# Check status
./setup-ollama.sh status

# View logs
./setup-ollama.sh logs

# Restart service
./setup-ollama.sh restart

# Stop service
./setup-ollama.sh stop
```

## Integration with Your Bot

The bot will automatically use the local LLM when `USE_LOCAL_LLM=true` is set in your environment.

The LocalLLMService connects to Ollama at `http://ollama:11434` and uses the `appointment-bot` model by default.

To switch between cloud and local LLM:
```bash
# Use local LLM
USE_LOCAL_LLM=true

# Use cloud LLM (OpenAI)
USE_LOCAL_LLM=false
```

## Performance Tips

1. **Model Selection**: Start with smaller models (7B) for faster response times
2. **GPU**: Use GPU if available for 10-50x speedup
3. **Quantization**: Use quantized models (Q4, Q5) for better performance
4. **Caching**: Ollama caches model contexts for faster subsequent requests
5. **Keep-alive**: Ollama keeps models loaded in memory for ~5 minutes after last use

## Resources

- Ollama Documentation: https://github.com/ollama/ollama
- Ollama Model Library: https://ollama.com/library
- Docker Compose Documentation: https://docs.docker.com/compose/

