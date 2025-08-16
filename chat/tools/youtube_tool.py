# chat/tools/youtube_tool.py
import json
import logging
import re
from typing import Any, Dict, List

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class YouTubeTool(BaseTool):
    def __init__(self, chat_service):
        self.chat_service = chat_service

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def description(self) -> str:
        return "Search for YouTube video recommendations or summarize YouTube videos"

    @property
    def triggers(self) -> List[str]:
        return [
            "youtube",
            "video",
            "watch",
            "recommend",
            "tutorial",
            "learn more",
            "show me videos",
            "find videos",
            "educational content",
        ]

    async def can_handle(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> float:
        message_lower = user_message.lower()

        # High confidence triggers
        high_confidence_patterns = [
            r"(find|show|recommend|suggest)\s+(me\s+)?(youtube|videos?|tutorials?)",
            r"youtube.*about",
            r"watch.*video",
            r"learn more.*video",
        ]

        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9

        # Medium confidence triggers
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.6

        # Learning/educational context suggests video might be helpful
        learning_keywords = ["learn", "tutorial", "how to", "guide", "instruction"]
        if any(keyword in message_lower for keyword in learning_keywords):
            return 0.4

        return 0.0

    async def execute(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> ToolResult:
        """Execute YouTube tool - either search for videos or summarize"""
        try:
            logger.info(f"YouTubeTool executing for query: {user_message[:100]}...")

            chat_service = chat_context.get("chat_service")
            if not chat_service:
                logger.error("Chat service not available in context")
                return ToolResult(success=False, error="Chat service not available")

            # Pass chat history for context
            chat_history = chat_context.get("messages_for_llm", [])
            response = await chat_service.get_youtube_agent_response(
                user_message, chat_history
            )

            logger.info(f"YouTube agent response type: {type(response)}")
            logger.info(
                f"YouTube agent response (first 200 chars): {str(response)[:200]}..."
            )

            # Try to parse as JSON for video recommendations
            try:
                video_data = json.loads(response)
                logger.info(
                    f"Successfully parsed JSON. Type: {type(video_data)}, Length: {len(video_data) if isinstance(video_data, list) else 'N/A'}"
                )

                if isinstance(video_data, list) and video_data:
                    # This is video recommendation data
                    logger.info("Returning video recommendations")
                    return ToolResult(
                        success=True,
                        content="Here are some YouTube video recommendations based on your query:",
                        message_type="youtube",
                        structured_data={"videos": video_data},  # Wrap list in a dict
                    )
                else:
                    logger.info("JSON parsed but not a valid video list")

            except json.JSONDecodeError as e:
                logger.info(f"JSON decode failed: {e}. Treating as text response.")

            # If not JSON or empty list, treat as text response (video summary)
            logger.info("Returning text response")
            return ToolResult(success=True, content=response, message_type="youtube")

        except Exception as e:
            logger.error(f"YouTube tool error: {e}", exc_info=True)
            return ToolResult(success=False, error=f"YouTube tool error: {str(e)}")
