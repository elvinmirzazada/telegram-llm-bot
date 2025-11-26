"""
Local LLM Service Integration

Handles communication with local Ollama LLM for natural language processing.
Extracts intent, entities, and generates conversational responses for appointment booking.
"""

import json
import logging
import requests
from datetime import datetime, date, timedelta
from typing import Any, Callable, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LocalLLMError(Exception):
    """Custom exception for Local LLM service errors."""
    pass


class LocalLLMService:
    """
    Service for interacting with local Ollama LLM.

    Handles intent extraction, entity recognition, and response generation
    for appointment booking conversations using a local model.
    """

    # Strong system prompt for appointment booking assistant
    SYSTEM_PROMPT = """You are an intelligent appointment booking assistant. Your primary role is to help users book, check, reschedule, or cancel appointments through natural conversation.

## Core Responsibilities:
1. Extract user intent from natural language
2. Identify and validate appointment details (date, time, service type)
3. Request missing information politely
4. Provide clear, helpful responses
5. Output structured JSON for system processing

## Supported Intents:
- **book_appointment**: User wants to create a new appointment
- **check_availability**: User wants to see available time slots
- **reschedule_appointment**: User wants to change an existing appointment
- **cancel_appointment**: User wants to cancel an appointment
- **smalltalk**: General conversation, greetings, or off-topic queries

## Date/Time Handling Rules:
- Accept natural language dates: "tomorrow", "next Monday", "December 15th", "11/25/2025"
- Accept time formats: "2pm", "14:00", "2:30 PM", "afternoon"
- Convert relative dates to absolute dates (use current date: November 25, 2025)
- Validate dates are in the future
- Business hours: 9:00 AM to 5:00 PM, Monday-Friday
- Appointment slots: 30-minute increments

## Response Format:
You MUST respond with VALID JSON only. No markdown, no explanations outside the JSON.

Required JSON structure:
{
    "intent": "book_appointment|check_availability|reschedule_appointment|cancel_appointment|smalltalk",
    "confidence": 0.0-1.0,
    "entities": {
        "date": "YYYY-MM-DD" or null,
        "time": "HH:MM" or null,
        "service_type": "string or null",
        "appointment_id": "integer or null"
    },
    "missing_info": ["list of missing required fields"],
    "user_message": "natural language response to user",
    "action": "proceed|ask_clarification|provide_info",
    "metadata": {
        "date_original": "user's original date expression",
        "time_original": "user's original time expression",
        "ambiguous_fields": []
    }
}

## Validation Rules:
- If date is missing for booking: add "date" to missing_info
- If time is missing for booking: add "time" to missing_info
- If date/time is ambiguous: set action to "ask_clarification"
- If intent is unclear: set confidence < 0.7 and ask clarifying question
- For cancellation: require appointment_id or date+time to identify appointment

## Important Notes:
- Always be polite and professional
- If user provides partial information, acknowledge what you have and ask for what's missing
- If you cannot understand the intent, set intent to "smalltalk" and ask for clarification
- NEVER make up information - only extract what the user provides
- Always output valid JSON
"""

    def __init__(
        self,
        repository_callback: Optional[Callable] = None,
        host: str = "http://localhost:11434",
        model: str = "llama3",
        temperature: float = 0.8,
        max_tokens: int = 1500,
    ):
        """
        Initialize Local LLM Service.

        Args:
            repository_callback: Callable for accessing repository functions
            host: Ollama server host URL
            model: Model name to use
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
        """
        self.host = host
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.repository_callback = repository_callback

        # Conversation context management
        self.conversation_context: Dict[str, Any] = {}

        logger.info(f"LocalLLMService initialized with model: {self.model} at {self.host}")

    async def generate_response(
        self,
        message: str,
        conversation_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate intelligent response based on user message.

        Args:
            message: User's input message
            conversation_state: Current conversation state/context

        Returns:
            Dictionary containing intent, entities, and response

        Raises:
            LocalLLMError: If LLM API call fails

        Example:
            >>> from app.services.local_llm import LocalLLMService
            >>> llm = LocalLLMService()
            >>> # result = await llm.generate_response(
            >>> #     "I want to book for tomorrow at 2pm",
            >>> #     conversation_state={"customer_id": 123}
            >>> # )
            >>> # print(result["intent"])
            "book_appointment"
        """
        try:
            # Build context for LLM
            context = self._build_context(message, conversation_state)

            # Send request to LLM
            response = await self._send_request_to_model(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=message,
                context=context,
            )

            # Parse and validate response
            parsed_response = self._parse_llm_response(response)

            # Enrich response with additional context
            enriched_response = await self._enrich_response(
                parsed_response, conversation_state
            )

            logger.info(
                f"Generated response for intent: {enriched_response.get('intent')} "
                f"with confidence: {enriched_response.get('confidence')}"
            )

            return enriched_response

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise LocalLLMError(f"Failed to generate response: {str(e)}") from e

    async def _send_request_to_model(
        self,
        system_prompt: str,
        user_message: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Send request to local Ollama LLM API.

        Args:
            system_prompt: System instructions for the model
            user_message: User's message
            context: Additional context for the conversation

        Returns:
            Raw response from the Ollama API

        Raises:
            LocalLLMError: If the API request fails
        """
        try:
            logger.debug(f"Sending request to local model: {self.model}")
            logger.debug(f"User message: {user_message}")
            logger.debug(f"Context: {context}")

            # Build the prompt with system instructions and context
            full_prompt = f"""{system_prompt}

                ## Current Context:
                {json.dumps(context, indent=2)}
                
                ## User Message:
                {user_message}
                
                ## Your Response (JSON only):
            """

            # Make request to Ollama API
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_ctx": self.max_tokens,
                        "num_predict": 200,
                    }
                },
                timeout=60
            )

            if response.status_code != 200:
                raise LocalLLMError(
                    f"Ollama API returned status {response.status_code}: {response.text}"
                )

            result = response.json()
            generated_text = result.get("response", "")

            if not generated_text:
                raise LocalLLMError("Empty response from Ollama API")

            logger.debug(f"Received response from model: {generated_text[:200]}...")
            return generated_text

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Ollama server at {self.host}: {e}")
            raise LocalLLMError(
                f"Cannot connect to Ollama server at {self.host}. "
                "Please ensure Ollama is running."
            ) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Request to Ollama timed out: {e}")
            raise LocalLLMError("Request to Ollama timed out") from e
        except Exception as e:
            logger.error(f"Error communicating with Ollama: {e}")
            raise LocalLLMError(f"Failed to communicate with Ollama: {str(e)}") from e

    def _build_context(
        self,
        message: str,
        conversation_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build context for LLM request.

        Args:
            message: Current user message
            conversation_state: Previous conversation state

        Returns:
            Context dictionary with relevant information
        """
        context = {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_time": datetime.now().strftime("%H:%M"),
            "business_hours": {
                "start": "09:00",
                "end": "17:00",
                "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            },
        }

        if conversation_state:
            context.update(
                {
                    "customer_id": conversation_state.get("customer_id"),
                    "conversation_history": conversation_state.get("history", []),
                    "last_intent": conversation_state.get("last_intent"),
                    "pending_action": conversation_state.get("pending_action"),
                }
            )

        return context

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse and validate LLM response.

        Args:
            response: Raw response from LLM

        Returns:
            Parsed and validated response dictionary

        Raises:
            LocalLLMError: If response is invalid or cannot be parsed
        """
        try:
            # Log the raw response for debugging
            logger.debug(f"Parsing LLM response: {response[:500]}")

            # Try to extract JSON from response
            # Remove markdown code blocks if present
            response_clean = response.strip()
            logger.info(response_clean)
            if response_clean.startswith("```"):
                # Remove ```json or ``` at start
                response_clean = response_clean.split('\n', 1)[1] if '\n' in response_clean else response_clean[3:]
                # Remove ``` at end
                if response_clean.endswith("```"):
                    response_clean = response_clean[:-3]

            # Find JSON object using regex as fallback
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
            else:
                # Try traditional approach
                json_start = response_clean.find('{')
                json_end = response_clean.rfind('}') + 1

                if json_start == -1 or json_end == 0:
                    raise ValueError("No JSON object found in response")

                json_str = response_clean[json_start:json_end]

            parsed = json.loads(json_str)

            # Validate required fields
            required_fields = ["intent", "confidence", "entities", "user_message", "action"]
            for field in required_fields:
                if field not in parsed:
                    logger.warning(f"Missing field {field}, adding default")
                    if field == "intent":
                        parsed["intent"] = "smalltalk"
                    elif field == "confidence":
                        parsed["confidence"] = 0.5
                    elif field == "entities":
                        parsed["entities"] = {"date": None, "time": None, "service_type": None, "appointment_id": None}
                    elif field == "user_message":
                        parsed["user_message"] = "I'm here to help with appointments."
                    elif field == "action":
                        parsed["action"] = "ask_clarification"

            # Validate intent
            valid_intents = [
                "book_appointment",
                "check_availability",
                "reschedule_appointment",
                "cancel_appointment",
                "smalltalk",
            ]
            if parsed["intent"] not in valid_intents:
                logger.warning(f"Unknown intent: {parsed['intent']}, defaulting to smalltalk")
                parsed["intent"] = "smalltalk"

            # Validate confidence
            if not 0 <= parsed["confidence"] <= 1:
                logger.warning(f"Invalid confidence: {parsed['confidence']}, clamping to range")
                parsed["confidence"] = max(0, min(1, parsed["confidence"]))

            # Validate entities structure
            if "entities" not in parsed or not isinstance(parsed["entities"], dict):
                parsed["entities"] = {
                    "date": None,
                    "time": None,
                    "service_type": None,
                    "appointment_id": None,
                }

            # Ensure missing_info is a list
            if "missing_info" not in parsed:
                parsed["missing_info"] = []

            # Ensure metadata exists
            if "metadata" not in parsed:
                parsed["metadata"] = {}

            logger.info(f"Successfully parsed intent: {parsed['intent']} with confidence: {parsed['confidence']}")
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response was: {response[:1000]}")

            # Fallback response
            return {
                "intent": "smalltalk",
                "confidence": 0.3,
                "entities": {
                    "date": None,
                    "time": None,
                    "service_type": None,
                    "appointment_id": None,
                },
                "missing_info": [],
                "user_message": "I'm sorry, I didn't quite understand that. Could you please rephrase?",
                "action": "ask_clarification",
                "metadata": {"parse_error": str(e)},
            }

    async def _enrich_response(
        self,
        parsed_response: Dict[str, Any],
        conversation_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Enrich response with repository data if available.

        Args:
            parsed_response: Parsed LLM response
            conversation_state: Current conversation state

        Returns:
            Enriched response with additional data
        """
        intent = parsed_response.get("intent")

        # If we have repository callback, fetch relevant data
        if self.repository_callback and intent == "check_availability":
            entities = parsed_response.get("entities", {})
            date_str = entities.get("date")

            if date_str:
                try:
                    # Parse date and fetch availability
                    appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    available_slots = await self.repository_callback(
                        "get_available_slots", date=appointment_date
                    )

                    # Add availability data to response
                    parsed_response["available_slots"] = available_slots
                    parsed_response["metadata"]["slots_fetched"] = True

                except Exception as e:
                    logger.error(f"Error fetching availability: {e}")
                    parsed_response["metadata"]["slots_error"] = str(e)

        return parsed_response

    def extract_date_time(self, text: str, reference_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Extract and normalize date/time from natural language.

        This is a helper method for parsing dates like "tomorrow", "next Monday", etc.

        Args:
            text: Text containing date/time information
            reference_date: Reference date for relative dates (defaults to today)

        Returns:
            Dictionary with normalized date and time

        Example:
            >>> result = llm.extract_date_time("tomorrow at 2pm")
            >>> print(result["date"])
            "2025-11-26"
        """
        if reference_date is None:
            reference_date = date.today()

        result = {"date": None, "time": None, "original_text": text}

        text_lower = text.lower()

        # Simple date extraction (can be enhanced with more sophisticated NLP)
        if "tomorrow" in text_lower:
            result["date"] = (reference_date + timedelta(days=1)).isoformat()
        elif "today" in text_lower:
            result["date"] = reference_date.isoformat()
        elif "next week" in text_lower:
            result["date"] = (reference_date + timedelta(days=7)).isoformat()

        # Simple time extraction
        import re

        time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",  # 2:30 pm
            r"(\d{1,2})\s*(am|pm)",  # 2pm
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0

                if len(match.groups()) >= 3 and match.group(3):
                    # Handle AM/PM
                    am_pm = match.group(3)
                    if am_pm == "pm" and hour < 12:
                        hour += 12
                    elif am_pm == "am" and hour == 12:
                        hour = 0

                result["time"] = f"{hour:02d}:{minute:02d}"
                break

        return result

    def validate_appointment_slot(
        self, date_str: str, time_str: str
    ) -> Dict[str, Any]:
        """
        Validate if the date/time is within business hours and in the future.

        Args:
            date_str: Date in YYYY-MM-DD format
            time_str: Time in HH:MM format

        Returns:
            Validation result with is_valid flag and messages
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

        try:
            appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            appointment_time = datetime.strptime(time_str, "%H:%M").time()
            appointment_datetime = datetime.combine(appointment_date, appointment_time)

            # Check if in the past
            if appointment_datetime <= datetime.now():
                result["is_valid"] = False
                result["errors"].append("Appointment must be in the future")

            # Check if weekend
            if appointment_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                result["is_valid"] = False
                result["errors"].append("Appointments are only available Monday-Friday")

            # Check business hours
            business_start = datetime.strptime("09:00", "%H:%M").time()
            business_end = datetime.strptime("17:00", "%H:%M").time()

            if appointment_time < business_start or appointment_time >= business_end:
                result["is_valid"] = False
                result["errors"].append(
                    "Appointment must be between 9:00 AM and 5:00 PM"
                )

            # Check if on 30-minute boundary
            if appointment_time.minute not in [0, 30]:
                result["warnings"].append(
                    "Appointments are available in 30-minute slots (e.g., 9:00, 9:30)"
                )

        except ValueError as e:
            result["is_valid"] = False
            result["errors"].append(f"Invalid date or time format: {str(e)}")

        return result
