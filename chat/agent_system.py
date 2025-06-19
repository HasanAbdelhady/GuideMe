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
        self.max_tools_per_message = 2   # Maximum tools to run simultaneously
    
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
            primary_tools_used = [r for r in tool_results if r.message_type != "background_process"]
            
            if not primary_tools_used:
                # No primary tools were used, get normal AI response
                ai_response = await self._get_normal_ai_response(user_message, chat_context)
            elif any(not r.success for r in primary_tools_used):
                # Some tools failed, provide fallback response
                ai_response = await self._get_normal_ai_response(user_message, chat_context)
                
            return ai_response, tool_results + background_results
            
        except Exception as e:
            logger.error(f"Agent system error: {e}", exc_info=True)
            # Fallback to normal AI response
            ai_response = await self._get_normal_ai_response(user_message, chat_context)
            return ai_response, []
    
    async def _select_and_execute_tools(self, user_message: str, chat_context: Dict[str, Any], active_modes: Dict[str, bool]) -> List[ToolResult]:
        """Select and execute the most appropriate tools for the user message, forcing execution if a mode is active."""
        
        # Check for forced tool execution via active modes
        forced_tool_name = None
        if active_modes.get('diagram'):
            forced_tool_name = 'diagram_generator'
        elif active_modes.get('youtube'):
            forced_tool_name = 'youtube'
        
        if forced_tool_name:
            tool_to_execute = next((t for t in self.tools if t.name == forced_tool_name), None)
            if tool_to_execute:
                logger.info(f"Mode '{forced_tool_name}' is active. Forcing execution of {tool_to_execute.name} tool.")
                try:
                    result = await tool_to_execute.execute(user_message, chat_context)
                    return [result]
                except Exception as e:
                    logger.error(f"Error executing forced tool {tool_to_execute.name}: {e}", exc_info=True)
                    return [ToolResult(success=False, error=f"Tool {tool_to_execute.name} failed: {str(e)}")]
            else:
                logger.warning(f"Mode '{forced_tool_name}' is active, but no tool with that name was found.")
                return []

        # If no mode is active, proceed with confidence-based selection
        logger.info("No single-functionality mode active. Using confidence scores to select tools.")
        
        # Get confidence scores from all tools
        tool_scores = []
        for tool in self.tools:
            try:
                confidence = await tool.can_handle(user_message, chat_context)
                if confidence >= self.confidence_threshold:
                    tool_scores.append((tool, confidence))
            except Exception as e:
                logger.error(f"Error getting confidence from {tool.name}: {e}")
        
        # Sort by confidence and select top tools
        tool_scores.sort(key=lambda x: x[1], reverse=True)
        selected_tools = tool_scores[:self.max_tools_per_message]
        
        if not selected_tools:
            logger.info("No tools selected for execution")
            return []
        
        logger.info(f"Selected tools: {[(tool.name, conf) for tool, conf in selected_tools]}")
        
        # Execute selected tools
        results = []
        for tool, confidence in selected_tools:
            try:
                # Skip background tools in primary execution
                if tool.name == "flashcard_concept_tracker":
                    continue
                    
                result = await tool.execute(user_message, chat_context)
                results.append(result)
                
                # Log tool usage
                logger.info(f"Tool {tool.name} executed with result: {result.success}")
                
            except Exception as e:
                logger.error(f"Error executing tool {tool.name}: {e}", exc_info=True)
                results.append(ToolResult(
                    success=False,
                    error=f"Tool {tool.name} failed: {str(e)}"
                ))
        
        return results
    
    async def _run_background_tools(self, user_message: str, chat_context: Dict[str, Any]) -> List[ToolResult]:
        """Run background tools like flashcard tracker"""
        background_results = []
        
        # Find background tools
        background_tools = [tool for tool in self.tools if tool.name == "flashcard_concept_tracker"]
        
        for tool in background_tools:
            try:
                confidence = await tool.can_handle(user_message, chat_context)
                if confidence > 0:
                    result = await tool.execute(user_message, chat_context)
                    background_results.append(result)
            except Exception as e:
                logger.error(f"Error in background tool {tool.name}: {e}", exc_info=True)
        
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
            logger.error(f"Error getting normal AI response: {e}", exc_info=True)
            return "I apologize, but I'm having trouble processing your request right now. Please try again."
    
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