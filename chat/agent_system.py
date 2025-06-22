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
        Process a user message and return AI response and tool results.
        Now supports streaming for better user experience.
        """
        logger.info(f"Processing message: {user_message[:100]}...")

        # Execute tools first
        tool_results = await self._select_and_execute_tools(user_message, chat_context, active_modes)

        # Run background tools
        background_results = await self._run_background_tools(user_message, chat_context)
        all_results = tool_results + background_results

        # Determine if we should use streaming for AI response
        should_stream = self._should_use_streaming(user_message, tool_results)

        # Generate AI response based on tool results
        ai_response = None
        successful_tools = [r for r in tool_results if r.success]

        if successful_tools:
            # Tools were used - provide contextual response
            ai_response = await self._get_contextual_ai_response(
                user_message, chat_context, successful_tools, stream=should_stream
            )
        else:
            # No tools used - provide normal AI response
            ai_response = await self._get_normal_ai_response(
                user_message, chat_context, stream=should_stream
            )

        # Check if AI response suggests creating diagrams and auto-generate them
        additional_tool_results = await self._auto_generate_suggested_diagrams(
            ai_response, user_message, chat_context
        )

        if additional_tool_results:
            # Add the auto-generated diagrams to the results
            all_results.extend(additional_tool_results)
            logger.info(
                f"Auto-generated {len(additional_tool_results)} diagrams from AI suggestions")

        logger.info(
            f"Processed message. Tools: {len(successful_tools)}, AI response: {'stream' if should_stream else 'string'}")
        return ai_response, all_results

    def _should_use_streaming(self, user_message: str, tool_results: List[ToolResult]) -> bool:
        """
        Determine if we should use streaming for the AI response based on the context
        """
        successful_tools = [r for r in tool_results if r.success]

        # Always stream if no tools are used (pure conversation)
        if len(successful_tools) == 0:
            return True

        # Stream if user is asking for explanations along with tools
        explanation_keywords = [
            'explain', 'what is', 'what are', 'how does', 'how do', 'why',
            'tell me about', 'describe', 'elaborate', 'detail'
        ]

        if any(keyword in user_message.lower() for keyword in explanation_keywords):
            return True

        # Stream if the message is long (likely complex)
        if len(user_message.split()) > 20:
            return True

        # Don't stream for simple tool requests
        return False

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

    async def _get_normal_ai_response(self, user_message: str, chat_context: Dict[str, Any], stream: bool = False) -> str:
        """Get a normal AI response without using tools"""
        try:
            # Use the existing AI service to get a normal response
            messages_for_llm = chat_context.get('messages_for_llm', [])
            messages_for_llm.append({"role": "user", "content": user_message})

            # New: Check for image data in the context
            image_data = chat_context.get('image_data')
            image_mime_type = chat_context.get('image_mime_type')
            vision_kwargs = {}
            if image_data and image_mime_type:
                vision_kwargs['image_data'] = image_data
                vision_kwargs['image_mime_type'] = image_mime_type
                logger.info(
                    "Passing image data to the AI service for a normal response.")

            if stream:
                # Return the stream object for streaming responses
                return await self.ai_service.get_ai_response_stream(
                    messages=messages_for_llm,
                    max_tokens=2000,  # Increased token limit for vision
                    temperature=0.7,
                    **vision_kwargs
                )
            else:
                response = await self.ai_service.get_ai_response(
                    messages=messages_for_llm,
                    max_tokens=2000,  # Increased token limit for vision
                    temperature=0.7,
                    **vision_kwargs
                )
                return response

        except Exception as e:
            logger.error(
                f"Error getting normal AI response: {e}", exc_info=True)
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    async def _get_contextual_ai_response(self, user_message: str, chat_context: Dict[str, Any], tool_results: List[ToolResult], stream: bool = False) -> str:
        """Get an AI response that provides context for the tools that were used"""
        try:
            # Create a summary of what tools were used
            successful_tools = [r for r in tool_results if r.success]

            # New: Check for image data to pass to contextual response
            image_data = chat_context.get('image_data')
            image_mime_type = chat_context.get('image_mime_type')
            vision_kwargs = {}
            if image_data and image_mime_type:
                vision_kwargs['image_data'] = image_data
                vision_kwargs['image_mime_type'] = image_mime_type
                logger.info(
                    "Passing image data to the AI service for a contextual response.")

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
                    return await self._generate_comprehensive_response(user_message, chat_context, successful_tools, stream, **vision_kwargs)

                # Otherwise, provide brief context
                return f""

            # For single tool usage, check if additional explanation is needed
            result = successful_tools[0]

            if additional_explanation_needed:
                # Generate comprehensive response even for single tool
                return await self._generate_comprehensive_response(user_message, chat_context, successful_tools, stream, **vision_kwargs)

            # Default brief responses for single tools

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

    async def _generate_comprehensive_response(self, user_message: str, chat_context: Dict[str, Any], tool_results: List[ToolResult], stream: bool = False, **kwargs) -> str:
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

            if stream:
                # Return the stream object for streaming responses
                return await self.ai_service.get_ai_response_stream(
                    messages=messages_for_comprehensive,
                    max_tokens=1500,  # Increased for vision
                    temperature=0.7,
                    **kwargs
                )
            else:
                response = await self.ai_service.get_ai_response(
                    messages=messages_for_comprehensive,
                    max_tokens=1500,  # Increased for vision
                    temperature=0.7,
                    **kwargs
                )
                logger.info(
                    f"Generated comprehensive response for mixed tool scenario with explanations")
                return response

        except Exception as e:
            logger.error(
                f"Error generating comprehensive response: {e}", exc_info=True)
            # Fallback to brief response
            return "I've provided the requested tools. Let me know if you need any clarification!"

    async def _auto_generate_suggested_diagrams(self, ai_response, user_message: str, chat_context: Dict[str, Any]) -> List[ToolResult]:
        """
        Detect when AI response suggests creating diagrams and automatically generate them.
        Returns list of additional tool results.
        """
        if not ai_response or hasattr(ai_response, '__iter__'):
            # Skip if no response or if it's a stream object
            return []

        # Convert response to string if it's not already
        response_text = str(ai_response) if ai_response else ""

        # Only very specific patterns that clearly indicate the AI wants to create a diagram
        # These should be explicit placeholders or clear diagram creation statements
        diagram_suggestion_patterns = [
            r'\[insert a.*?diagram.*?\]',
            r'\[create a.*?diagram.*?\]',
            r'\[add a.*?diagram.*?\]',
            r'\[display a.*?diagram.*?\]',
            r'\[draw a.*?diagram.*?\]',
            r'\[include a.*?diagram.*?\]',
            r'\[insert a.*?chart.*?\]',
            r'\[create a.*?chart.*?\]',
            r'\[create a.*?flowchart.*?\]',
            r'\[insert a.*?visual.*?\]',
            # Be very specific with action statements to avoid false positives
            r'let me create a specific diagram',
            r'i\'ll create a diagram showing',
            r'here\'s a diagram that shows',
            r'i\'ll draw a diagram to illustrate',
        ]

        import re
        response_lower = response_text.lower()
        diagram_suggestions = []

        for pattern in diagram_suggestion_patterns:
            matches = re.finditer(pattern, response_lower,
                                  re.IGNORECASE | re.DOTALL)
            for match in matches:
                suggestion_text = match.group(0)
                diagram_suggestions.append({
                    'text': suggestion_text,
                    'start': match.start(),
                    'end': match.end()
                })

        if not diagram_suggestions:
            return []

        # Additional filter: Skip if the original user message was just expressing preference about diagrams
        user_message_lower = user_message.lower()
        preference_indicators = [
            'i would like', 'i\'d like', 'i want to see', 'i prefer', 'i enjoy',
            'i appreciate', 'i love', 'more diagrams', 'throughout the session',
            'in general', 'going forward', 'from now on', 'in the future'
        ]

        if any(indicator in user_message_lower for indicator in preference_indicators):
            logger.info(
                "Skipping auto-diagram generation - user was expressing preference, not requesting specific diagram")
            return []

        logger.info(
            f"Found {len(diagram_suggestions)} diagram suggestions in AI response")

        # Get the diagram tool
        diagram_tool = next(
            (tool for tool in self.tools if tool.name == 'diagram_generator'), None)
        if not diagram_tool:
            logger.warning("Diagram tool not found for auto-generation")
            return []

        additional_results = []

        for suggestion in diagram_suggestions:
            try:
                # Extract context around the suggestion for better diagram generation
                suggestion_context = self._extract_diagram_context(
                    response_text, suggestion)

                # Create a diagram query based on the context
                diagram_query = f"Create a diagram for: {suggestion_context}. Based on the discussion: {user_message}"

                logger.info(
                    f"Auto-generating diagram for: {suggestion['text'][:50]}...")

                # Execute the diagram tool
                result = await diagram_tool.execute(diagram_query, chat_context)
                if result.success:
                    result.execution_order = 999  # Put auto-generated diagrams at the end
                    additional_results.append(result)
                    logger.info("Successfully auto-generated diagram")
                else:
                    logger.warning(
                        f"Failed to auto-generate diagram: {result.error}")

            except Exception as e:
                logger.error(
                    f"Error auto-generating diagram: {e}", exc_info=True)

        return additional_results

    def _extract_diagram_context(self, response_text: str, suggestion: Dict[str, Any]) -> str:
        """Extract relevant context around a diagram suggestion for better diagram generation"""
        start_pos = max(0, suggestion['start'] - 200)  # 200 chars before
        # 200 chars after
        end_pos = min(len(response_text), suggestion['end'] + 200)

        context = response_text[start_pos:end_pos]

        # Clean up the context
        context = context.replace(suggestion['text'], '').strip()

        # Extract the most relevant sentence
        sentences = context.split('.')
        if sentences:
            # Find the sentence that mentions key diagram-related words
            diagram_keywords = ['structure', 'process', 'flow', 'relationship',
                                'hierarchy', 'model', 'framework', 'architecture']

            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in diagram_keywords):
                    return sentence.strip()

            # If no specific sentence found, return the first non-empty sentence
            for sentence in sentences:
                if sentence.strip() and len(sentence.strip()) > 10:
                    return sentence.strip()

        return context[:100] + "..." if len(context) > 100 else context

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
