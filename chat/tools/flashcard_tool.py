# chat/tools/flashcard_tool.py
from .base import BaseTool, ToolResult
from typing import Dict, Any, List
import re
import logging
from ..models import ChatFlashcard
import json
from django.db import IntegrityError
import asyncio
import os
import google.generativeai as genai
from asgiref.sync import sync_to_async

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
        logger.warning("FLASHCARD API key for Gemini not found. FlashcardTool will be disabled.")
except Exception as e:
    gemini_model = None
    logger.error(f"Error configuring Gemini for FlashcardTool: {e}")

class FlashcardTool(BaseTool):
    def __init__(self, ai_service):
        self.ai_service = ai_service # Kept for consistent initialization signature
        self.gemini_model = gemini_model
        # Common words to ignore when detecting concepts
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me',
            'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'am',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall'
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
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        if not self.gemini_model:
            return 0.0 # Disable if Gemini isn't configured

        # This tool runs as a background process for every message
        # It analyzes the conversation for new concepts
        message_length = len(user_message.split())
        
        # Only process substantial messages
        if message_length < 5:
            return 0.0
            
        # Higher confidence for educational/explanatory content
        educational_indicators = ['explain', 'definition', 'means', 'refers to', 'concept', 'theory', 'principle']
        if any(indicator in user_message.lower() for indicator in educational_indicators):
            return 0.8
            
        # Medium confidence for technical or complex discussions
        if message_length > 15:
            return 0.6
            
        return 0.4  # Default background processing
    
    async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
        try:
            logger.info(f"FlashcardTool background processing for message: {user_message[:50]}...")
            
            # Get recent conversation history for context
            recent_messages = chat_context.get('messages_for_llm', [])[-5:]  # Last 5 messages
            conversation_text = "\\n".join([msg.get('content', '') for msg in recent_messages])
            
            # Extract concepts from the conversation
            concepts = await self._extract_concepts(user_message, conversation_text)
            
            flashcards_created = 0
            if concepts:
                for term, definition in concepts.items():
                    created = await self._create_flashcard_if_new(
                        term=term,
                        definition=definition,
                        chat=chat_context['chat'],
                        context=user_message
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
                        "concepts_added": list(concepts.keys())
                    }
                )
            else:
                return ToolResult(
                    success=True,
                    content="",  # Silent background process
                    message_type="background_process",
                    metadata={"tool_used": "flashcard_concept_tracker", "flashcards_created": 0}
                )
                
        except Exception as e:
            logger.error(f"FlashcardTool error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Flashcard processing error: {str(e)}"
            )
    
    async def _extract_concepts(self, user_message: str, conversation_context: str) -> Dict[str, str]:
        """Use AI to extract key concepts and their definitions from the conversation"""
        if not self.gemini_model:
            return {}
            
        try:
            prompt = f"""
            Analyze the following conversation and extract key concepts that would be valuable for learning flashcards.
            For each concept, provide a clear, concise definition.
            
            Focus on:
            - Technical terms and their meanings
            - Important concepts being explained
            - New vocabulary being introduced
            - Processes or methods being described
            
            Conversation:
            {conversation_context}
            
            Latest message:
            {user_message}
            
            Return the response in this exact JSON format:
            {{
                "concept_name": "clear definition of the concept",
                "another_concept": "another definition"
            }}
            
            Only include concepts that have clear definitions in the conversation. If no concepts are found, return an empty JSON object {{}}.
            """
            
            response = await sync_to_async(self.gemini_model.generate_content)(prompt)
            response_text = response.text
            
            # Find the start and end of the JSON object to isolate it from surrounding text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end > json_start:
                json_string = response_text[json_start:json_end+1].strip()
                concepts = json.loads(json_string)
                return concepts if isinstance(concepts, dict) else {}
            
            logger.warning(f"Could not find a valid JSON object in the flashcard LLM response: {response_text}")
            return {}

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse concepts JSON: {response_text}")
            return {}
                
        except Exception as e:
            logger.error(f"Error extracting concepts: {e}", exc_info=True)
            return {}
    
    async def _create_flashcard_if_new(self, term: str, definition: str, chat, context: str) -> bool:
        """Create a flashcard if the concept doesn't already exist"""
        try:
            # Clean up the term
            term = term.strip().title()
            definition = definition.strip()
            
            if len(term) < 2 or len(definition) < 10:
                return False
                
            # Check if flashcard already exists
            existing = await ChatFlashcard.objects.filter(
                chat=chat,
                term__iexact=term
            ).afirst()
            
            if not existing:
                await ChatFlashcard.objects.acreate(
                    chat=chat,
                    term=term,
                    definition=definition,
                    context=context[:500],  # Limit context length
                    auto_generated=True
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