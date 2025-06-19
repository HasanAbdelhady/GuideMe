from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    content: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    # text, diagram, quiz, youtube, flashcard_update, background_process
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # Order in which this tool was requested by the user
    execution_order: Optional[int] = None


class BaseTool(ABC):
    """Base class for all chat tools"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for agent decision making"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this tool does"""
        pass

    @property
    @abstractmethod
    def triggers(self) -> List[str]:
        """Keywords/phrases that might trigger this tool"""
        pass

    @abstractmethod
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        """Return confidence score (0-1) that this tool should be used"""
        pass

    @abstractmethod
    async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
        """Execute the tool and return results"""
        pass
