# chat/tools/quiz_tool.py
from .base import BaseTool, ToolResult
from typing import Dict, Any, List
import re
import logging
from ..models import ChatQuestionBank
from django.utils.html import strip_tags
import json

logger = logging.getLogger(__name__)

class QuizTool(BaseTool):
    def __init__(self, chat_service):
        self.chat_service = chat_service
    
    @property
    def name(self) -> str:
        return "quiz_generator"
    
    @property
    def description(self) -> str:
        return "Creates interactive quizzes to test understanding of topics discussed"
    
    @property
    def triggers(self) -> List[str]:
        return [
            "quiz", "test", "question", "practice", "check understanding",
            "assess me", "make questions", "test my knowledge"
        ]
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        message_lower = user_message.lower()
        
        # High confidence triggers
        high_confidence_patterns = [
            r"(create|make|generate)\s+(a\s+)?(quiz|test|questions?)",
            r"test\s+(my\s+)?(knowledge|understanding)",
            r"quiz\s+me",
            r"check\s+(my\s+)?understanding"
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9
                
        # Medium confidence triggers
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.7
            
        # Assessment context
        assessment_keywords = ["practice", "review", "study", "prepare"]
        if any(keyword in message_lower for keyword in assessment_keywords):
            return 0.5
            
        return 0.0
    
    async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
        try:
            logger.info(f"QuizTool executing for query: {user_message[:100]}...")
            
            quiz_data = await self.chat_service.generate_quiz_from_query(
                chat_history_messages=chat_context.get('messages_for_llm', []),
                user_query=user_message,
                chat_id=chat_context['chat'].id,
                user_id=chat_context['user'].id
            )
            
            if quiz_data and quiz_data.get('quiz_html'):
                # Save quiz questions to question bank
                await self._save_quiz_to_question_bank(
                    quiz_data=quiz_data,
                    chat=chat_context['chat'],
                    user_message=user_message
                )
                
                return ToolResult(
                    success=True,
                    content="Quiz generated based on our conversation:",
                    message_type="quiz",
                    structured_data=quiz_data,
                    metadata={
                        "tool_used": "quiz_generator",
                        "saved_to_question_bank": True
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    error="Failed to generate quiz"
                )
        except Exception as e:
            logger.error(f"QuizTool error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Quiz generation error: {str(e)}"
            )
    
    async def _save_quiz_to_question_bank(self, quiz_data: Dict[str, Any], chat, user_message: str):
        """Extract and save individual questions to the question bank"""
        try:
            quiz_html = quiz_data.get('quiz_html', '')
            
            # Parse quiz HTML to extract individual questions
            # This is a simplified approach - you might want to enhance this
            questions = self._extract_questions_from_html(quiz_html)
            
            for question_data in questions:
                try:
                    # Check if this question already exists
                    existing = await ChatQuestionBank.objects.filter(
                        chat=chat,
                        question_text=question_data['text']
                    ).afirst()
                    
                    if not existing:
                        await ChatQuestionBank.objects.acreate(
                            chat=chat,
                            question_html=question_data['html'],
                            question_text=question_data['text'],
                            correct_answer=question_data['correct_answer'],
                            topic=self._extract_topic_from_message(user_message),
                            difficulty='medium'  # Default, could be enhanced
                        )
                except Exception as db_error:
                    # Database table might not exist yet (migration not run)
                    logger.warning(f"Question bank save skipped (table might not exist): {db_error}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error saving quiz to question bank: {e}", exc_info=True)
    
    def _extract_questions_from_html(self, quiz_html: str) -> List[Dict[str, Any]]:
        """Extract individual questions from quiz HTML"""
        # This is a simplified implementation
        # You'll want to enhance this based on your exact quiz HTML structure
        questions = []
        
        # For now, treat the entire quiz as one question
        # In a real implementation, you'd parse the HTML properly
        plain_text = strip_tags(quiz_html)
        
        questions.append({
            'html': quiz_html,
            'text': plain_text[:200] + "..." if len(plain_text) > 200 else plain_text,
            'correct_answer': 'A'  # You'd extract this from the actual quiz
        })
        
        return questions
    
    def _extract_topic_from_message(self, user_message: str) -> str:
        """Extract topic from user message for categorization"""
        # Simple implementation - extract first few meaningful words
        words = user_message.split()
        meaningful_words = [w for w in words[:5] if len(w) > 3 and w.lower() not in ['quiz', 'test', 'make', 'create']]
        return " ".join(meaningful_words[:3]) if meaningful_words else "General" 