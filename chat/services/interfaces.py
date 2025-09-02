# chat/services/interfaces.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from django.http import StreamingHttpResponse


class FileProcessingServiceInterface(ABC):
    """Interface for file processing operations"""

    @abstractmethod
    def extract_text_from_uploaded_file(
        self, uploaded_file, max_chars: int = 15000
    ) -> Dict[str, Any]:
        """Extract text from uploaded files"""
        pass

    @abstractmethod
    def save_file(self, chat_id: str, uploaded_file) -> Optional[str]:
        """Save uploaded file and return path"""
        pass


class MessageServiceInterface(ABC):
    """Interface for message-related operations"""

    @abstractmethod
    def create_message(self, chat, role: str, content: str):
        """Create a new message"""
        pass

    @abstractmethod
    def get_chat_history(self, chat, limit: int = 20) -> List:
        """Get chat history"""
        pass

    @abstractmethod
    def update_chat_title(self, chat, title_text: Optional[str] = None):
        """Update chat title"""
        pass


class AICompletionServiceInterface(ABC):
    """Interface for AI completion operations"""

    @abstractmethod
    def enforce_token_limit(
        self, messages: List[Dict], max_tokens: int = 6000
    ) -> List[Dict]:
        """Enforce token limits on messages"""
        pass

    @abstractmethod
    async def get_completion(
        self,
        messages: List[Dict],
        query: Optional[str] = None,
        max_tokens: int = 6500,
        chat_id: Optional[str] = None,
        is_new_chat: bool = False,
        attached_file_name: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Get AI completion"""
        pass

    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict],
        query: Optional[str] = None,
        max_tokens: int = 6000,
        chat_id: Optional[str] = None,
        is_new_chat: bool = False,
        attached_file_name: Optional[str] = None,
    ):
        """Stream AI completion"""
        pass


class RAGServiceInterface(ABC):
    """Interface for RAG operations"""

    @abstractmethod
    async def get_files_rag(self, chat_id: str) -> List:
        """Get RAG files for a chat"""
        pass


class YouTubeServiceInterface(ABC):
    """Interface for YouTube operations"""

    @abstractmethod
    async def get_agent_response(
        self, query: str, chat_history: List[Dict[str, str]]
    ) -> str:
        """Get YouTube agent response"""
        pass


class DiagramServiceInterface(ABC):
    """Interface for diagram generation"""

    @abstractmethod
    async def generate_diagram_image(
        self,
        chat_history_messages: List[Dict],
        user_query: str,
        chat_id: str,
        user_id: str,
    ) -> Optional[str]:
        """Generate diagram image and return diagram ID"""
        pass


class QuizServiceInterface(ABC):
    """Interface for quiz generation"""

    @abstractmethod
    async def generate_quiz_from_query(
        self,
        chat_history_messages: List[Dict[str, str]],
        user_query: str,
        chat_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate quiz from query"""
        pass

    @abstractmethod
    async def generate_quiz(
        self, chat_history_messages: List[Dict[str, str]], chat_id: str, **kwargs
    ) -> Dict[str, Any]:
        """Generate general quiz"""
        pass
