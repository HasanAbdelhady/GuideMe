# chat/agent_system.py
from typing import Dict, Any, List, Optional, Tuple
import logging
import asyncio
from .tools import BaseTool, ToolResult, DiagramTool, YouTubeTool, QuizTool, FlashcardTool
from .ai_models import AIService

logger = logging.getLogger(__name__)


class ChatAgentSystem:
    """Intelligent agent system that coordinates tools and decides when to use them"""

    def __init__(self, chat_service, ai_service: AIService):
        self.chat_service = chat_service
        self.ai_service = ai_service

        # Initialize all tools
        self.tools: List[BaseTool] = [
            DiagramTool(chat_service),
            YouTubeTool(chat_service),
            QuizTool(chat_service),
            FlashcardTool(ai_service)
        ]

        # Tool selection parameters
        self.confidence_threshold = 0.5  # Minimum confidence to activate a tool
        self.max_tools_per_message = 5   # Increased to allow more tools simultaneously

    async def process_message(
        self,
        user_message: str,
        chat_context: Dict[str, Any],
        active_modes: Dict[str, bool]
    ) -> Tuple[Optional[str], List[ToolResult]]:
        """
        Process a user message and decide whether to use tools

        Args:
            user_message: The user's input
            chat_context: Full chat context including history, user, chat object
            active_modes: Dict of currently active modes {rag: bool, diagram: bool, youtube: bool}

        Returns:
            Tuple of (normal_ai_response, tool_results)
        """
        try:
            logger.info(f"Agent processing message: {user_message[:100]}...")

            # Agent mode is active - analyze and potentially use tools
            tool_results = await self._select_and_execute_tools(user_message, chat_context, active_modes)

            # Always run background tools (like flashcard tracker)
            background_results = await self._run_background_tools(user_message, chat_context)

            # Determine if we need a normal AI response
            ai_response = None
            primary_tools_used = [
                r for r in tool_results if r.message_type != "background_process"]

            # Always get an AI response to provide context and explanation for the tools used
            if primary_tools_used:
                # If tools were used, create a contextual AI response
                ai_response = await self._get_contextual_ai_response(user_message, chat_context, primary_tools_used)
            else:
                # No primary tools were used, get normal AI response
                ai_response = await self._get_normal_ai_response(user_message, chat_context)

            return ai_response, tool_results + background_results

        except Exception as e:
            logger.error(f"Agent system error: {e}", exc_info=True)
            # Fallback to normal AI response
            ai_response = await self._get_normal_ai_response(user_message, chat_context)
            return ai_response, []

    async def _select_and_execute_tools(self, user_message: str, chat_context: Dict[str, Any], active_modes: Dict[str, bool]) -> List[ToolResult]:
        """Select and execute the most appropriate tools for the user message, allowing multiple tools to run simultaneously."""

        # Check for forced tool execution via active modes
        forced_tools = []
        if active_modes.get('diagram'):
            forced_tools.append('diagram_generator')
        if active_modes.get('youtube'):
            forced_tools.append('youtube')

        # If specific modes are active, force those tools but still allow others to run
        selected_tools_with_confidence = []

        if forced_tools:
            for forced_tool_name in forced_tools:
                tool_to_execute = next(
                    (t for t in self.tools if t.name == forced_tool_name), None)
                if tool_to_execute:
                    logger.info(
                        f"Mode '{forced_tool_name}' is active. Adding {tool_to_execute.name} tool to execution list.")
                    selected_tools_with_confidence.append(
                        # High confidence for forced tools
                        (tool_to_execute, 1.0))
                else:
                    logger.warning(
                        f"Mode '{forced_tool_name}' is active, but no tool with that name was found.")

        # Always check confidence scores for all tools (even when modes are active)
        logger.info(
            "Checking confidence scores for all tools to allow mixed tool usage.")

        for tool in self.tools:
            # Skip if already added as forced tool
            if any(tool.name == forced_name for forced_name in forced_tools):
                continue

            try:
                confidence = await tool.can_handle(user_message, chat_context)
                if confidence >= self.confidence_threshold:
                    selected_tools_with_confidence.append((tool, confidence))
            except Exception as e:
                logger.error(f"Error getting confidence from {tool.name}: {e}")

        # Sort by confidence and select tools (increased limit)
        selected_tools_with_confidence.sort(key=lambda x: x[1], reverse=True)
        selected_tools = selected_tools_with_confidence[:self.max_tools_per_message]

        if not selected_tools:
            logger.info("No tools selected for execution")
            return []

        logger.info(
            f"Selected tools for simultaneous execution: {[(tool.name, conf) for tool, conf in selected_tools]}")

        # Execute all selected tools simultaneously
        results = []
        for tool, confidence in selected_tools:
            try:
                # Skip background tools in primary execution
                if tool.name == "flashcard_concept_tracker":
                    continue

                result = await tool.execute(user_message, chat_context)
                results.append(result)

                # Log tool usage
                logger.info(
                    f"Tool {tool.name} executed with result: {result.success}")

            except Exception as e:
                logger.error(
                    f"Error executing tool {tool.name}: {e}", exc_info=True)
                results.append(ToolResult(
                    success=False,
                    error=f"Tool {tool.name} failed: {str(e)}"
                ))

        return results

    async def _run_background_tools(self, user_message: str, chat_context: Dict[str, Any]) -> List[ToolResult]:
        """Run background tools like flashcard tracker"""
        background_results = []

        # Find background tools
        background_tools = [
            tool for tool in self.tools if tool.name == "flashcard_concept_tracker"]

        for tool in background_tools:
            try:
                confidence = await tool.can_handle(user_message, chat_context)
                if confidence > 0:
                    result = await tool.execute(user_message, chat_context)
                    background_results.append(result)
            except Exception as e:
                logger.error(
                    f"Error in background tool {tool.name}: {e}", exc_info=True)

        return background_results

    async def _get_normal_ai_response(self, user_message: str, chat_context: Dict[str, Any]) -> str:
        """Get a normal AI response without using tools"""
        try:
            # Use the existing AI service to get a normal response
            messages_for_llm = chat_context.get('messages_for_llm', [])
            messages_for_llm.append({"role": "user", "content": user_message})

            response = await self.ai_service.get_ai_response(
                messages=messages_for_llm,
                max_tokens=1000,
                temperature=0.7
            )

            return response

        except Exception as e:
            logger.error(
                f"Error getting normal AI response: {e}", exc_info=True)
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    async def _get_contextual_ai_response(self, user_message: str, chat_context: Dict[str, Any], tool_results: List[ToolResult]) -> str:
        """Get an AI response that provides context for the tools that were used"""
        try:
            # Create a summary of what tools were used
            successful_tools = [r for r in tool_results if r.success]

            # For mixed content with multiple tools, provide minimal context to avoid redundancy
            if len(successful_tools) > 1:
                tool_types = []
                has_quiz = False
                for result in successful_tools:
                    if result.message_type == "diagram":
                        tool_types.append("diagram")
                    elif result.message_type == "youtube":
                        tool_types.append("video recommendations")
                    elif result.message_type == "quiz":
                        tool_types.append("interactive quiz")
                        has_quiz = True
                    else:
                        tool_types.append(result.message_type)

                # Very brief response for mixed content - let the tools speak for themselves
                tools_used = ", ".join(tool_types)

                # Special handling when quiz is involved - avoid any explanatory content
                if has_quiz:
                    return f"Here's your {tools_used} as requested!"
                else:
                    return f"Here's your {tools_used} as requested!"

            # For single tool usage, provide more detailed context but avoid duplication
            result = successful_tools[0]

            # Special handling for quiz tool - minimal response to avoid duplication
            if result.message_type == "quiz":
                return "Here's your interactive quiz based on our conversation:"

            # Handle other single tools normally
            if result.message_type == "diagram":
                return "Here's the diagram you requested:"
            elif result.message_type == "youtube":
                if result.structured_data and 'videos' in result.structured_data:
                    return "Here are some relevant video recommendations:"
                else:
                    return "Here's a summary of that YouTube video:"
            else:
                return f"Here's your {result.message_type} as requested:"

        except Exception as e:
            logger.error(
                f"Error getting contextual AI response: {e}", exc_info=True)
            return "I've prepared the requested content for you."

    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get information about available tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "triggers": ", ".join(tool.triggers)
            }
            for tool in self.tools
        ]
