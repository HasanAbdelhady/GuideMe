# chat/services/message_service.py
import logging
from typing import List, Optional

from ..models import Message
from .interfaces import MessageServiceInterface


class MessageService(MessageServiceInterface):
    """Service for handling message-related operations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_message(self, chat, role: str, content: str):
        """Create a new message in the database"""
        return Message.objects.create(chat=chat, role=role, content=content)

    def get_chat_history(self, chat, limit: int = 20) -> List:
        """Get chat history with optional limit"""
        return list(chat.messages.all().order_by("created_at"))[-limit:]

    def update_chat_title(self, chat, title_text: Optional[str] = None):
        """Update chat title with truncation"""
        if not title_text:
            return
        chat.title = title_text[:50] + ("..." if len(title_text) > 50 else "")
        chat.save()
