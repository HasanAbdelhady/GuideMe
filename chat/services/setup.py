# chat/services/setup.py
"""
Service container setup and configuration.
This module initializes and configures all services with proper dependency injection.
"""

from .ai_completion import AICompletionService
from .container import get_container
from .diagram_service import DiagramService
from .file_processing import FileProcessingService
from .interfaces import (
    AICompletionServiceInterface,
    DiagramServiceInterface,
    FileProcessingServiceInterface,
    MessageServiceInterface,
    QuizServiceInterface,
    RAGServiceInterface,
    YouTubeServiceInterface,
)
from .message_service import MessageService
from .quiz_service import QuizService
from .rag_service import RAGService
from .youtube_service import YouTubeService


def setup_services():
    """Initialize and configure all services in the container"""
    container = get_container()

    # Register services as singletons for better performance and state management
    container.register_singleton(RAGServiceInterface, RAGService())
    container.register_singleton(
        FileProcessingServiceInterface, FileProcessingService()
    )
    container.register_singleton(MessageServiceInterface, MessageService())
    container.register_singleton(YouTubeServiceInterface, YouTubeService())
    container.register_singleton(QuizServiceInterface, QuizService())

    # AI Completion Service depends on RAG Service
    rag_service = container.get(RAGServiceInterface)
    container.register_singleton(
        AICompletionServiceInterface, AICompletionService(rag_service)
    )

    # Diagram Service depends on AI Completion Service
    ai_completion_service = container.get(AICompletionServiceInterface)
    container.register_singleton(
        DiagramServiceInterface, DiagramService(ai_completion_service)
    )

    return container


def get_service(interface):
    """Get a service from the container"""
    container = get_container()
    return container.get(interface)
