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

    async def _detect_tool_order_from_message(self, user_message: str) -> List[str]:
        """
        Analyze the user message to determine the order in which tools were requested.
        Returns a list of tool names in the order they appear in the message.
        """
        tool_keywords = {
            'diagram_generator': ['diagram', 'chart', 'graph', 'visual', 'draw', 'flowchart', 'mindmap', 'show me a diagram'],
            'youtube': ['video', 'youtube', 'recommend', 'watch', 'videos', 'explain', 'tutorial'],
            'quiz': ['quiz', 'test', 'question', 'assess', 'check', 'evaluate', 'quiz me']
        }

        message_lower = user_message.lower()
        tool_positions = []

        for tool_name, keywords in tool_keywords.items():
            for keyword in keywords:
                pos = message_lower.find(keyword)
                if pos != -1:
                    tool_positions.append((pos, tool_name))
                    break  # Found this tool, move to next

        # Sort by position in message and remove duplicates while preserving order
        tool_positions.sort(key=lambda x: x[0])
        ordered_tools = []
        seen_tools = set()

        for pos, tool_name in tool_positions:
            if tool_name not in seen_tools:
                ordered_tools.append(tool_name)
                seen_tools.add(tool_name)

        logger.info(f"Detected tool order from message: {ordered_tools}")
        return ordered_tools

    async def _select_and_execute_tools(self, user_message: str, chat_context: Dict[str, Any], active_modes: Dict[str, bool]) -> List[ToolResult]:
        """Select and execute the most appropriate tools for the user message, maintaining the requested order."""

        # Detect the order tools were requested in the user message
        requested_tool_order = await self._detect_tool_order_from_message(user_message)

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

        # Execute all selected tools simultaneously but preserve order information
        execution_tasks = []
        tool_order_map = {}

        for tool, confidence in selected_tools:
            try:
                # Skip background tools in primary execution
                if tool.name == "flashcard_concept_tracker":
                    continue

                # Determine the order index for this tool
                if tool.name in requested_tool_order:
                    order_index = requested_tool_order.index(tool.name)
                else:
                    # If tool wasn't explicitly requested, put it at the end
                    order_index = len(requested_tool_order) + \
                        len(execution_tasks)

                tool_order_map[tool.name] = order_index

                # Create async task for tool execution
                task = asyncio.create_task(
                    tool.execute(user_message, chat_context))
                execution_tasks.append((tool, task, order_index))

            except Exception as e:
                logger.error(
                    f"Error setting up execution for tool {tool.name}: {e}", exc_info=True)

        # Wait for all tools to complete
        results_with_order = []
        for tool, task, order_index in execution_tasks:
            try:
                result = await task
                # Add order information to the result
                result.execution_order = order_index
                results_with_order.append((result, order_index))

                logger.info(
                    f"Tool {tool.name} executed with result: {result.success}, order: {order_index}")

            except Exception as e:
                logger.error(
                    f"Error executing tool {tool.name}: {e}", exc_info=True)
                error_result = ToolResult(
                    success=False,
                    error=f"Tool {tool.name} failed: {str(e)}"
                )
                error_result.execution_order = order_index
                results_with_order.append((error_result, order_index))

        # Sort results by the requested order
        results_with_order.sort(key=lambda x: x[1])
        ordered_results = [result for result,
                           order_index in results_with_order]

        logger.info(
            f"Returning {len(ordered_results)} tool results in requested order")
        return ordered_results

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

            # Check if user is asking for additional explanations beyond tool functionality
            additional_explanation_needed = self._needs_additional_explanation(
                user_message, successful_tools)

            # For mixed content with multiple tools
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

                # If user asked for additional explanation, provide comprehensive response
                if additional_explanation_needed:
                    # Generate full AI response that includes both tool context and explanations
                    return await self._generate_comprehensive_response(user_message, chat_context, successful_tools)

                # Otherwise, provide brief context
                tools_used = ", ".join(tool_types)
                return f"Here's your {tools_used} as requested!"

            # For single tool usage, check if additional explanation is needed
            result = successful_tools[0]

            if additional_explanation_needed:
                # Generate comprehensive response even for single tool
                return await self._generate_comprehensive_response(user_message, chat_context, successful_tools)

            # Default brief responses for single tools
            if result.message_type == "quiz":
                return "Here's your interactive quiz based on our conversation:"
            elif result.message_type == "diagram":
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

    def _needs_additional_explanation(self, user_message: str, tool_results: List[ToolResult]) -> bool:
        """
        Determine if the user is asking for explanations beyond what tools provide
        """
        # Keywords that indicate user wants explanations
        explanation_keywords = [
            'explain', 'explanation', 'what is', 'what are', 'define', 'definition',
            'concept of', 'how does', 'how do', 'why', 'tell me about', 'describe',
            'meaning of', 'understand', 'clarify', 'elaborate', 'detail'
        ]

        # Tool-related keywords that we can ignore for explanation detection
        tool_keywords = [
            'quiz', 'test', 'question', 'video', 'youtube', 'recommend',
            'diagram', 'chart', 'visual', 'graph'
        ]

        message_lower = user_message.lower()

        # Check if message contains explanation requests
        has_explanation_request = any(
            keyword in message_lower for keyword in explanation_keywords)

        if not has_explanation_request:
            return False

        # More sophisticated check: look for explanation requests that aren't about tool functionality
        # Split the message by common conjunctions to analyze different parts
        message_parts = []
        for separator in [' then ', ' and ', ' also ', ' plus ', ' after ', ' before ']:
            if separator in message_lower:
                message_parts = message_lower.split(separator)
                break

        if not message_parts:
            message_parts = [message_lower]

        # Check if any part of the message asks for explanations beyond tool requests
        for part in message_parts:
            part = part.strip()
            # If this part has explanation keywords but no tool keywords, it needs explanation
            if any(keyword in part for keyword in explanation_keywords):
                if not any(tool_keyword in part for tool_keyword in tool_keywords):
                    logger.info(f"Detected explanation request in: '{part}'")
                    return True

        return False

    async def _generate_comprehensive_response(self, user_message: str, chat_context: Dict[str, Any], tool_results: List[ToolResult]) -> str:
        """
        Generate a comprehensive AI response that addresses both tool results and additional explanations
        """
        try:
            # Create context about what tools were used
            tool_summary = []
            for result in tool_results:
                if result.message_type == "quiz":
                    tool_summary.append("generated an interactive quiz")
                elif result.message_type == "youtube":
                    tool_summary.append("provided video recommendations")
                elif result.message_type == "diagram":
                    tool_summary.append("created a diagram")
                else:
                    tool_summary.append(f"used {result.message_type} tool")

            tools_description = " and ".join(tool_summary)

            # Create a prompt for comprehensive response
            messages_for_llm = chat_context.get('messages_for_llm', [])

            # Add context about tools being used
            enhanced_user_message = f"""The user requested: "{user_message}"

I have {tools_description} based on their request. However, they also seem to be asking for additional explanations or information beyond what these tools provide.

Please provide a comprehensive response that:
1. Briefly acknowledges the tools I've provided 
2. Addresses any additional explanations, concepts, or information they requested
3. Maintains a natural, conversational tone

Focus especially on explaining any concepts, definitions, or "what is" questions they may have asked."""

            messages_for_comprehensive = messages_for_llm + [
                {"role": "user", "content": enhanced_user_message}
            ]

            response = await self.ai_service.get_ai_response(
                messages=messages_for_comprehensive,
                max_tokens=800,
                temperature=0.7
            )

            logger.info(
                f"Generated comprehensive response for mixed tool scenario with explanations")
            return response

        except Exception as e:
            logger.error(
                f"Error generating comprehensive response: {e}", exc_info=True)
            # Fallback to brief response
            return "I've provided the requested tools. Let me know if you need any clarification!"

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
