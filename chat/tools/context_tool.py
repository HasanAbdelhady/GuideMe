# chat/tools/context_tool.py
import logging
import re
from typing import Any, Dict, List

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ContextTool(BaseTool):
    def __init__(self, chat_service):
        self.chat_service = chat_service

    @property
    def name(self) -> str:
        return "context"

    @property
    def description(self) -> str:
        return "Query uploaded documents using RAG (Retrieval Augmented Generation)"

    @property
    def triggers(self) -> List[str]:
        return [
            "according to",
            "based on",
            "from the document",
            "in the file",
            "what does the document say",
            "search",
            "find",
            "reference",
        ]

    async def can_handle(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> float:
        # Only suggest if there are uploaded documents in this chat
        chat = chat_context.get("chat")
        if not chat:
            return 0.0

        # Check if chat has any uploaded documents
        has_documents = await chat.rag_files.aexists()
        if not has_documents:
            return 0.0

        message_lower = user_message.lower()

        # High confidence triggers when explicitly referencing documents
        high_confidence_patterns = [
            r"(according to|based on|from)\s+(the\s+)?(document|file|paper|pdf)",
            r"what does (the|my) (document|file|paper) say",
            r"find.*in.*document",
            r"search.*document",
        ]

        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9

        # Medium confidence for general search terms when documents exist
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.6

        # Low confidence for questions that could benefit from context
        question_words = ["what", "how", "why", "when", "where", "who", "explain"]
        if (
            any(word in message_lower for word in question_words)
            and len(user_message.split()) > 5
        ):
            return 0.4

        return 0.0

    async def execute(self, user_message: str, chat_context: dict) -> ToolResult:
        """Execute context tool for RAG queries"""
        try:
            files_rag_instance = chat_context.get("files_rag_instance")
            if not files_rag_instance:
                return ToolResult(
                    success=False,
                    error="No RAG context available. Please upload documents first.",
                )

            # Use the retrieve method from LangChainRAG
            rag_response = files_rag_instance.retrieve(user_message)

            if not rag_response or not rag_response.strip():
                return ToolResult(
                    success=False,
                    error="No relevant information found in the uploaded documents.",
                )

            return ToolResult(success=True, content=rag_response, message_type="text")

        except Exception as e:
            logger.error(f"Context tool error: {e}", exc_info=True)
            return ToolResult(success=False, error=f"RAG query error: {str(e)}")
