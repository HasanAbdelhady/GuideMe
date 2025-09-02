# chat/services/rag_service.py
import logging
from typing import List

from asgiref.sync import sync_to_async

from ..models import Chat
from .interfaces import RAGServiceInterface


class RAGService(RAGServiceInterface):
    """Service for handling RAG (Retrieval-Augmented Generation) operations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_files_rag(self, chat_id: str) -> List:
        """Return the RAG files for this chat instance"""
        try:
            chat = await sync_to_async(Chat.objects.get)(id=chat_id)
            rag_files = await sync_to_async(list)(
                chat.rag_files.select_related("user").all()
            )
            return rag_files
        except Chat.DoesNotExist:
            return []
