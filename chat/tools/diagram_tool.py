# chat/tools/diagram_tool.py
import logging
import re
from typing import Any, Dict, List

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class DiagramTool(BaseTool):
    def __init__(self, diagram_service):
        self.diagram_service = diagram_service

    @property
    def name(self) -> str:
        return "diagram_generator"

    @property
    def description(self) -> str:
        return "Creates visual diagrams to explain complex concepts, processes, or relationships"

    @property
    def triggers(self) -> List[str]:
        return [
            "diagram",
            "chart",
            "visualize",
            "draw",
            "flowchart",
            "architecture",
            "process flow",
            "explain visually",
            "visual representation",
        ]

    async def can_handle(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> float:
        message_lower = user_message.lower()

        # High confidence triggers
        high_confidence_patterns = [
            r"(create|make|generate|draw|show)\s+(a\s+)?(diagram|chart|flowchart)",
            r"visualize",
            r"show me (how|the process|the flow|the architecture)",
            r"explain (visually|with a diagram)",
        ]

        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9

        # Medium confidence triggers
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.6

        # Low confidence for complex explanations
        if len(user_message.split()) > 10 and any(
            word in message_lower
            for word in ["process", "workflow", "architecture", "system"]
        ):
            return 0.3

        return 0.0

    async def execute(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> ToolResult:
        try:
            logger.info(f"DiagramTool executing for query: {user_message[:100]}...")

            diagram_id = await self.diagram_service.generate_diagram_image(
                chat_history_messages=chat_context.get("messages_for_llm", []),
                user_query=user_message,
                chat_id=str(chat_context["chat"].id),
                user_id=str(chat_context["user"].id),
            )

            if diagram_id:
                return ToolResult(
                    success=True,
                    content=f"Diagram generated for: {user_message[:100]}",
                    message_type="diagram",
                    structured_data={"diagram_image_id": str(diagram_id)},
                    metadata={"tool_used": "diagram_generator"},
                )
            else:
                return ToolResult(success=False, error="Failed to generate diagram")
        except Exception as e:
            logger.error(f"DiagramTool error: {e}", exc_info=True)
            return ToolResult(
                success=False, error=f"Diagram generation error: {str(e)}"
            )
