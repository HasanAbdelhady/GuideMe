# chat/tools/flashcard_tool.py
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List

from django.db import IntegrityError

import google.generativeai as genai
from asgiref.sync import sync_to_async

from ..models import ChatFlashcard
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Configure Gemini
try:
    FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
    if FLASHCARD_API_KEY:
        genai.configure(api_key=FLASHCARD_API_KEY)
        # Using a fast and capable model for this task
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    else:
        gemini_model = None
        logger.warning(
            "FLASHCARD API key for Gemini not found. FlashcardTool will be disabled."
        )
except Exception as e:
    gemini_model = None
    logger.error(f"Error configuring Gemini for FlashcardTool: {e}")


class FlashcardTool(BaseTool):
    def __init__(self, ai_service):
        self.ai_service = ai_service  # Kept for consistent initialization signature
        self.gemini_model = gemini_model
        # Common words to ignore when detecting concepts
        self.stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
            "am",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "shall",
        }

    @property
    def name(self) -> str:
        return "flashcard_concept_tracker"

    @property
    def description(self) -> str:
        return "Automatically identifies and creates flashcards for new concepts discussed in the conversation"

    @property
    def triggers(self) -> List[str]:
        return []  # This tool runs in background, no explicit triggers

    async def can_handle(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> float:
        if not self.gemini_model:
            return 0.0  # Disable if Gemini isn't configured

        # Skip meta-instructions immediately
        if self._is_meta_instruction(user_message):
            return 0.0

        # This tool runs as a background process for educational content
        message_length = len(user_message.split())

        # Only process substantial messages
        if message_length < 5:
            return 0.0

        # Skip if the message is clearly a command or request
        message_lower = user_message.lower()
        command_indicators = [
            "create",
            "make",
            "generate",
            "show me",
            "tell me",
            "can you",
            "please",
        ]
        if any(message_lower.startswith(indicator) for indicator in command_indicators):
            return 0.0

        # Higher confidence for educational/explanatory content
        educational_indicators = [
            "definition",
            "means",
            "refers to",
            "concept",
            "theory",
            "principle",
            "process",
            "mechanism",
            "algorithm",
            "formula",
            "equation",
            "structure",
            "function",
            "property",
            "characteristic",
            "flashcards",
            "explain",
            "flashcards",
        ]
        if any(indicator in message_lower for indicator in educational_indicators):
            return 0.8

        # Look for scientific/technical domains
        scientific_domains = [
            "biology",
            "chemistry",
            "physics",
            "mathematics",
            "computer science",
            "engineering",
            "medical",
            "anatomy",
            "neuroscience",
            "genetics",
        ]
        if any(domain in message_lower for domain in scientific_domains):
            return 0.7

        # Medium confidence for technical or complex discussions with substance
        if message_length > 20 and not any(
            word in message_lower for word in ["diagram", "video", "quiz", "flashcard"]
        ):
            return 0.5

        # Lower confidence for shorter technical content
        if message_length > 10:
            return 0.3

        return 0.0  # Skip very short messages

    async def execute(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> ToolResult:
        try:
            logger.info(
                f"FlashcardTool background processing for message: {user_message[:50]}..."
            )

            # Get recent conversation history for context
            recent_messages = chat_context.get("messages_for_llm", [])[
                -5:
            ]  # Last 5 messages
            conversation_text = "\\n".join(
                [msg.get("content", "") for msg in recent_messages]
            )

            # Extract concepts from the conversation
            concepts = await self._extract_concepts(user_message, conversation_text)

            flashcards_created = 0
            if concepts:
                for term, definition in concepts.items():
                    created = await self._create_flashcard_if_new(
                        term=term,
                        definition=definition,
                        chat=chat_context["chat"],
                        context=user_message,
                    )
                    if created:
                        flashcards_created += 1

            if flashcards_created > 0:
                return ToolResult(
                    success=True,
                    content=f"Added {flashcards_created} new concept(s) to your flashcard vault",
                    message_type="background_process",
                    metadata={
                        "tool_used": "flashcard_concept_tracker",
                        "flashcards_created": flashcards_created,
                        "concepts_added": list(concepts.keys()),
                    },
                )
            else:
                return ToolResult(
                    success=True,
                    content="",  # Silent background process
                    message_type="background_process",
                    metadata={
                        "tool_used": "flashcard_concept_tracker",
                        "flashcards_created": 0,
                    },
                )

        except Exception as e:
            logger.error(f"FlashcardTool error: {e}", exc_info=True)
            return ToolResult(
                success=False, error=f"Flashcard processing error: {str(e)}"
            )

    async def _extract_concepts(
        self, user_message: str, conversation_context: str
    ) -> Dict[str, str]:
        """Use AI to extract key concepts and their definitions from the conversation"""
        if not self.gemini_model:
            return {}

        try:
            # Filter out obvious meta-instructions and conversational noise
            if self._is_meta_instruction(user_message):
                logger.info(
                    f"Skipping flashcard extraction for meta-instruction: {user_message[:50]}..."
                )
                return {}

            prompt = f"""
            Analyze the following conversation and extract ONLY scientific, technical, or educational concepts that would be valuable for learning flashcards.
            
            STRICT RULES - DO NOT create flashcards for:
            - User interface instructions (like "create diagram", "recommend videos", "make quiz")
            - Conversation management ("explain more", "tell me about", "show me")
            - Learning preferences or styles
            - Tool or system functionality
            - Generic requests or commands
            - Meta-conversation about the chat itself
            
            ONLY CREATE FLASHCARDS FOR:
            - Scientific terms and definitions (e.g., "photosynthesis", "neural network")
            - Technical concepts with clear explanations (e.g., "machine learning", "DNA replication")
            - Mathematical or logical principles (e.g., "derivative", "algorithm")
            - Academic subject matter being taught or explained
            - Processes, theories, or laws from specific domains (physics, chemistry, biology, etc.)
            
            The concept must have a clear, factual definition provided in the conversation content.
            
            Conversation:
            {conversation_context}
            
            Latest message:
            {user_message}
            
            Return the response in this exact JSON format:
            {{
                "concept_name": "clear definition of the concept",
                "another_concept": "another definition"
            }}
            
            Only include concepts that:
            1. Are scientific/technical/educational in nature
            2. Have clear definitions provided in the conversation
            3. Are NOT meta-instructions or conversation management
            
            IMPORTANT:
            - MAKE SURE THE DEFINITIONS ARE CLEAR AND CONCISE AND NO MORE THAN 12 WORDS.
            If no valid educational concepts are found, return an empty JSON object {{}}.
            """

            response = await sync_to_async(self.gemini_model.generate_content)(prompt)
            response_text = response.text

            # Find the start and end of the JSON object to isolate it from surrounding text
            json_start = response_text.find("{")
            json_end = response_text.rfind("}")

            if json_start != -1 and json_end > json_start:
                json_string = response_text[json_start: json_end + 1].strip()
                concepts = json.loads(json_string)

                # Additional filtering for quality control
                filtered_concepts = {}
                for term, definition in (
                    concepts.items() if isinstance(concepts, dict) else []
                ):
                    if self._is_valid_educational_concept(term, definition):
                        filtered_concepts[term] = definition
                    else:
                        logger.info(
                            f"Filtered out non-educational concept: {term}")

                return filtered_concepts

            logger.warning(
                f"Could not find a valid JSON object in the flashcard LLM response: {response_text}"
            )
            return {}

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse concepts JSON: {response_text}")
            return {}

        except Exception as e:
            logger.error(f"Error extracting concepts: {e}", exc_info=True)
            return {}

    def _is_meta_instruction(self, message: str) -> bool:
        """Check if the message is a meta-instruction that should not generate flashcards"""
        message_lower = message.lower().strip()

        # Common meta-instruction patterns
        meta_patterns = [
            # Tool requests
            "create a diagram",
            "make a diagram",
            "show me a diagram",
            "generate diagram",
            "recommend videos",
            "find videos",
            "youtube videos",
            "video recommendations",
            "create quiz",
            "make quiz",
            "quiz me",
            "generate quiz",
            "create flashcard",
            "make flashcard",
            # Conversation management
            "explain more",
            "tell me more",
            "continue explaining",
            "go on",
            "can you",
            "could you",
            "please",
            "i want",
            "i need",
            "show me",
            "tell me about",
            "what is your",
            "how do you",
            # Learning preferences
            "learning style",
            "prefer to learn",
            "learning preference",
            "teaching style",
            "explain in a way",
            # System/interface related
            "upload file",
            "attach file",
            "load document",
            "use rag",
            "mode active",
            "turn on",
            "enable",
            "disable",
        ]

        # Check for exact matches or if message starts with these patterns
        for pattern in meta_patterns:
            if pattern in message_lower or message_lower.startswith(pattern):
                return True

        # Check if message is very short and likely a command
        if len(message.split()) <= 3 and any(
            word in message_lower
            for word in ["create", "make", "show", "tell", "explain", "generate"]
        ):
            return True

        return False

    def _is_valid_educational_concept(self, term: str, definition: str) -> bool:
        """Additional validation to ensure the concept is educational"""
        term_lower = term.lower()
        definition_lower = definition.lower()

        # Filter out terms that are clearly not educational concepts
        invalid_terms = [
            "diagram",
            "video",
            "quiz",
            "recommendation",
            "style",
            "preference",
            "user",
            "chat",
            "conversation",
            "request",
            "instruction",
            "mode",
            "system",
            "tool",
            "feature",
            "interface",
        ]

        # Check if the term itself is invalid
        for invalid in invalid_terms:
            if invalid in term_lower:
                return False

        # Check if definition contains meta-language
        meta_definition_indicators = [
            "user wants",
            "user requests",
            "conversation about",
            "chat feature",
            "tool that",
            "system that",
            "way to",
            "method for explaining",
            "type of request",
            "kind of instruction",
        ]

        for indicator in meta_definition_indicators:
            if indicator in definition_lower:
                return False

        # Ensure minimum quality standards
        if len(term) < 2 or len(definition) < 15:
            return False

        # Must contain some educational/scientific indicators
        educational_indicators = [
            "process",
            "theory",
            "principle",
            "law",
            "formula",
            "equation",
            "mechanism",
            "structure",
            "function",
            "property",
            "characteristic",
            "concept",
            "method",
            "technique",
            "phenomenon",
            "reaction",
            "system",
            "model",
            "algorithm",
            "protocol",
            "procedure",
        ]

        has_educational_content = any(
            indicator in definition_lower for indicator in educational_indicators
        )

        # Allow scientific/technical terms even without explicit indicators
        scientific_domains = [
            "biology",
            "chemistry",
            "physics",
            "mathematics",
            "computer",
            "engineering",
            "medical",
            "scientific",
            "technical",
            "academic",
            "research",
            "computer science",
            "data science",
            "machine learning",
            "deep learning",
            "artificial intelligence",
            "neural network",
            "reinforcement learning",
            "natural language processing",
            "computer vision",
            "robotics",
            "cybersecurity",
            "blockchain",
            "quantum computing",
            "genetic algorithms",
            "evolutionary algorithms",
            "fuzzy logic",
            "expert systems",
            "knowledge management",
            "knowledge representation",
            "knowledge acquisition",
            "knowledge base",
            "knowledge engineering",
            "knowledge management system",
        ]

        has_scientific_context = any(
            domain in definition_lower for domain in scientific_domains
        )

        return has_educational_content or has_scientific_context

    async def _create_flashcard_if_new(
        self, term: str, definition: str, chat, context: str
    ) -> bool:
        """Create a flashcard if the concept doesn't already exist"""
        try:
            # Clean up the term
            term = term.strip().title()
            definition = definition.strip()

            if len(term) < 2 or len(definition) < 10:
                return False

            # Check if flashcard already exists
            existing = await ChatFlashcard.objects.filter(
                chat=chat, term__iexact=term
            ).afirst()

            if not existing:
                await ChatFlashcard.objects.acreate(
                    chat=chat,
                    term=term,
                    definition=definition,
                    context=context[:500],  # Limit context length
                    auto_generated=True,
                )
                logger.info(f"Created flashcard for concept: {term}")
                return True
            return False

        except IntegrityError:
            # Concept already exists
            return False
        except Exception as e:
            logger.error(f"Error creating flashcard: {e}", exc_info=True)
            return False
