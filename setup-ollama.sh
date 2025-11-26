#!/bin/bash
# Setup script for Ollama service in Docker
# This script helps you set up and manage Ollama for local LLM inference

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Ollama Docker Setup Script ===${NC}\n"

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is running${NC}"
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
        echo -e "${RED}Error: docker-compose is not installed.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ docker-compose is available${NC}"
}

# Function to start Ollama service
start_ollama() {
    echo -e "\n${YELLOW}Starting Ollama service...${NC}"
    docker-compose up -d ollama

    echo -e "${YELLOW}Waiting for Ollama to be ready...${NC}"
    sleep 10

    # Check if Ollama is running
    if docker ps | grep -q telegram_bot_ollama; then
        echo -e "${GREEN}✓ Ollama service is running${NC}"
    else
        echo -e "${RED}✗ Failed to start Ollama service${NC}"
        exit 1
    fi
}

# Function to pull the model
pull_model() {
    local model_name=${1:-"llama3"}

    echo -e "\n${YELLOW}Pulling model: ${model_name}${NC}"

    docker exec telegram_bot_ollama ollama pull ${model_name} || {
        echo -e "${RED}Failed to pull model '${model_name}'.${NC}"
        echo -e "${YELLOW}Please check the model name and try again.${NC}"
        return 1
    }

    echo -e "${GREEN}✓ Model '${model_name}' is ready${NC}"
}

# Function to list available models
list_models() {
    echo -e "\n${YELLOW}Available models in Ollama:${NC}"
    docker exec telegram_bot_ollama ollama list
}

# Function to create a custom model
create_custom_model() {
    echo -e "\n${YELLOW}Creating custom 'llama3-appointment' model based on llama3...${NC}"

    # First, pull llama3 base model
    echo -e "${YELLOW}Pulling llama3 base model...${NC}"
    docker exec telegram_bot_ollama ollama pull llama3

    # Create a temporary Modelfile
    cat > /tmp/Modelfile << 'EOF'
FROM llama3

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
EOF

    # Copy Modelfile to container
    docker cp /tmp/Modelfile telegram_bot_ollama:/tmp/Modelfile

    # Create the model
    docker exec telegram_bot_ollama ollama create llama3-appointment -f /tmp/Modelfile

    echo -e "${GREEN}✓ Custom model 'llama3-appointment' created${NC}"
    echo -e "${YELLOW}Note: You can also use 'llama3' directly as specified in your config${NC}"

    # Clean up
    rm /tmp/Modelfile
}

# Function to test the model
test_model() {
    local model_name=${1:-"llama3"}

    echo -e "\n${YELLOW}Testing model: ${model_name}${NC}"
    echo -e "${YELLOW}Sending test prompt...${NC}\n"

    docker exec telegram_bot_ollama ollama run ${model_name} "I want to book an appointment tomorrow at 2pm"
}

# Function to show Ollama logs
show_logs() {
    echo -e "\n${YELLOW}Showing Ollama logs (Ctrl+C to exit):${NC}\n"
    docker logs -f telegram_bot_ollama
}

# Function to stop Ollama
stop_ollama() {
    echo -e "\n${YELLOW}Stopping Ollama service...${NC}"
    docker-compose stop ollama
    echo -e "${GREEN}✓ Ollama service stopped${NC}"
}

# Function to restart Ollama
restart_ollama() {
    echo -e "\n${YELLOW}Restarting Ollama service...${NC}"
    docker-compose restart ollama
    sleep 5
    echo -e "${GREEN}✓ Ollama service restarted${NC}"
}

# Function to check Ollama status
check_status() {
    echo -e "\n${YELLOW}Checking Ollama status...${NC}\n"

    if docker ps | grep -q telegram_bot_ollama; then
        echo -e "${GREEN}✓ Ollama container is running${NC}"

        # Check if API is responding
        if docker exec telegram_bot_ollama curl -s http://localhost:11434/api/tags > /dev/null; then
            echo -e "${GREEN}✓ Ollama API is responding${NC}"
        else
            echo -e "${RED}✗ Ollama API is not responding${NC}"
        fi

        # Show available models
        list_models
    else
        echo -e "${RED}✗ Ollama container is not running${NC}"
    fi
}

# Main menu
show_menu() {
    echo -e "\n${GREEN}=== Ollama Management Menu ===${NC}"
    echo "1. Start Ollama service"
    echo "2. Pull/Download a model"
    echo "3. Create custom 'llama3-appointment' model"
    echo "4. List available models"
    echo "5. Test a model"
    echo "6. Check Ollama status"
    echo "7. View Ollama logs"
    echo "8. Restart Ollama service"
    echo "9. Stop Ollama service"
    echo "10. Full setup (start + create model)"
    echo "0. Exit"
    echo -e "\nEnter your choice: "
}

# Parse command line arguments
case "${1:-menu}" in
    start)
        check_docker
        check_docker_compose
        start_ollama
        ;;
    pull)
        pull_model "${2:-llama3}"
        ;;
    create)
        create_custom_model
        ;;
    list)
        list_models
        ;;
    test)
        test_model "${2:-llama3}"
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    restart)
        restart_ollama
        ;;
    stop)
        stop_ollama
        ;;
    setup)
        check_docker
        check_docker_compose
        start_ollama
        sleep 5
        pull_model "llama3"
        echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
        echo -e "Ollama is ready to use with the 'llama3' model."
        echo -e "${YELLOW}You can optionally create a custom model with: ./setup-ollama.sh create${NC}"
        ;;
    menu)
        check_docker
        check_docker_compose

        while true; do
            show_menu
            read -r choice

            case $choice in
                1) start_ollama ;;
                2)
                    echo "Enter model name (default: llama3): "
                    read -r model
                    pull_model "${model:-llama3}"
                    ;;
                3) create_custom_model ;;
                4) list_models ;;
                5)
                    echo "Enter model name to test (default: llama3): "
                    read -r model
                    test_model "${model:-llama3}"
                    ;;
                6) check_status ;;
                7) show_logs ;;
                8) restart_ollama ;;
                9) stop_ollama ;;
                10)
                    start_ollama
                    sleep 5
                    pull_model "llama3"
                    echo -e "\n${GREEN}Setup complete! llama3 model is ready.${NC}"
                    ;;
                0)
                    echo -e "\n${GREEN}Goodbye!${NC}"
                    exit 0
                    ;;
                *)
                    echo -e "${RED}Invalid choice. Please try again.${NC}"
                    ;;
            esac

            echo -e "\nPress Enter to continue..."
            read -r
        done
        ;;
    *)
        echo "Usage: $0 {start|pull|create|list|test|status|logs|restart|stop|setup|menu}"
        echo ""
        echo "Commands:"
        echo "  start              - Start Ollama service"
        echo "  pull [model]       - Pull a model from Ollama registry (default: llama3)"
        echo "  create             - Create custom 'llama3-appointment' model"
        echo "  list               - List available models"
        echo "  test [model]       - Test a model with sample prompt (default: llama3)"
        echo "  status             - Check Ollama service status"
        echo "  logs               - View Ollama logs"
        echo "  restart            - Restart Ollama service"
        echo "  stop               - Stop Ollama service"
        echo "  setup              - Full setup (start + pull llama3)"
        echo "  menu               - Interactive menu (default)"
        exit 1
        ;;
esac

