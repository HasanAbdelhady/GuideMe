# chat/services/youtube_service.py
import logging
from typing import Dict, List

from asgiref.sync import sync_to_async

from ..agent_service import run_youtube_agent
from .interfaces import YouTubeServiceInterface


class YouTubeService(YouTubeServiceInterface):
    """Service for handling YouTube-related operations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_agent_response(
        self, query: str, chat_history: List[Dict[str, str]]
    ) -> str:
        """
        Runs the YouTube agent for a given query and returns the result.
        This is an async wrapper around the synchronous agent execution.
        """
        self.logger.info(f"Passing query to YouTube agent: {query}")
        try:
            # Use sync_to_async to run the synchronous agent function in an async context
            response = await sync_to_async(run_youtube_agent, thread_sensitive=False)(
                query, chat_history
            )
            return response
        except Exception as e:
            self.logger.error(
                f"Error calling YouTube agent via sync_to_async: {e}", exc_info=True
            )
            return "An error occurred while communicating with the YouTube agent."
