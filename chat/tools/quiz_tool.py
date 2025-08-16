# chat/tools/quiz_tool.py
import logging
import re
from typing import Any, Dict, List

from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup

from ..models import ChatQuestionBank
from .base import BaseTool, ToolResult

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
            "quiz",
            "test",
            "question",
            "practice",
            "check understanding",
            "assess me",
            "make questions",
            "test my knowledge",
        ]

    async def can_handle(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> float:
        message_lower = user_message.lower()

        # High confidence triggers
        high_confidence_patterns = [
            r"(create|make|generate)\s+(a\s+)?(quiz|test|questions?)",
            r"test\s+(my\s+)?(knowledge|understanding)",
            r"quiz\s+me",
            r"check\s+(my\s+)?understanding",
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

    async def execute(
        self, user_message: str, chat_context: Dict[str, Any]
    ) -> ToolResult:
        try:
            logger.info(
                f"QuizTool executing for query: {user_message[:100]}...")

            quiz_data = await self.chat_service.generate_quiz_from_query(
                chat_history_messages=chat_context.get("messages_for_llm", []),
                user_query=user_message,
                chat_id=chat_context["chat"].id,
                user_id=chat_context["user"].id,
            )

            if quiz_data and quiz_data.get("quiz_html"):
                # Save quiz questions to question bank
                await self._save_quiz_to_question_bank(
                    quiz_data=quiz_data,
                    chat=chat_context["chat"],
                    user_message=user_message,
                )

                # Separate content and quiz_html properly
                content_text = quiz_data.get(
                    "content", "Here's your interactive quiz:")

                # Ensure we have clean content text
                if not content_text or len(content_text.strip()) < 5:
                    content_text = "Here's your interactive quiz:"

                return ToolResult(
                    success=True,
                    content=content_text,  # Only text content goes here
                    message_type="quiz",
                    # Only HTML goes here
                    structured_data={"quiz_html": quiz_data["quiz_html"]},
                    metadata={
                        "tool_used": "quiz_generator",
                        "saved_to_question_bank": True,
                        "content_separated": True,
                    },
                )
            else:
                error_msg = (
                    quiz_data.get("error", "Failed to generate quiz")
                    if quiz_data
                    else "Failed to generate quiz"
                )
                return ToolResult(success=False, error=error_msg)
        except Exception as e:
            logger.error(f"QuizTool error: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Quiz generation error: {str(e)}")

    async def _save_quiz_to_question_bank(
        self, quiz_data: Dict[str, Any], chat, user_message: str
    ):
        """Extract and save individual questions to the question bank"""
        try:
            quiz_html = quiz_data.get("quiz_html", "")
            logger.info(
                f"Saving quiz to question bank. HTML length: {len(quiz_html)}")

            # Parse quiz HTML to extract individual questions
            questions = self._extract_questions_from_html(quiz_html)
            logger.info(f"Extracted {len(questions)} questions from quiz HTML")

            saved_count = 0
            for question_data in questions:
                try:
                    # Check if this question already exists (using sync_to_async)
                    existing = await sync_to_async(
                        lambda: ChatQuestionBank.objects.filter(
                            chat=chat, question_text=question_data["text"]
                        ).first()
                    )()

                    if not existing:
                        await sync_to_async(ChatQuestionBank.objects.create)(
                            chat=chat,
                            question_html=question_data["html"],
                            question_text=question_data["text"],
                            correct_answer=question_data["correct_answer"],
                            topic=self._extract_topic_from_message(
                                user_message),
                            difficulty="medium",  # Default, could be enhanced
                        )
                        saved_count += 1
                        logger.info(
                            f"Saved question to bank: {question_data['text'][:50]}..."
                        )
                    else:
                        logger.info(
                            f"Question already exists in bank: {question_data['text'][:50]}..."
                        )

                except Exception as db_error:
                    logger.error(
                        f"Error saving individual question to bank: {db_error}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"Successfully saved {saved_count} new questions to question bank"
            )

        except Exception as e:
            logger.error(
                f"Error saving quiz to question bank: {e}", exc_info=True)

    def _extract_questions_from_html(self, quiz_html: str) -> List[Dict[str, Any]]:
        """Extract individual questions from quiz HTML using BeautifulSoup."""
        questions = []
        try:
            soup = BeautifulSoup(quiz_html, "html.parser")
            question_divs = soup.find_all("div", class_="quiz-question")
            logger.info(
                f"Found {len(question_divs)} quiz-question divs in HTML")

            for i, div in enumerate(question_divs):
                # Ensure each question has a unique name for its radio buttons
                form = div.find("form")
                if form:
                    for radio in form.find_all("input", type="radio"):
                        radio["name"] = f"q_{i + 1}"  # Start from q_1

                question_text_div = div.find(
                    "div", class_="font-semibold mb-1")
                if not question_text_div:
                    # Try alternative selectors
                    question_text_div = div.find("div", class_="font-semibold")
                    if not question_text_div:
                        question_text_div = div.find("p")

                question_text = (
                    question_text_div.get_text(strip=True)
                    if question_text_div
                    else f"Question {i + 1}"
                )

                correct_answer = div.get("data-correct", "").upper()
                if not correct_answer:
                    logger.warning(
                        f"No correct answer found for question {i + 1}")

                questions.append(
                    {
                        "html": str(div),
                        "text": question_text,
                        "correct_answer": correct_answer,
                    }
                )

                logger.info(
                    f"Extracted question {i + 1}: {question_text[:30]}... (Correct: {correct_answer})"
                )

        except Exception as e:
            logger.error(
                f"Error parsing quiz HTML with BeautifulSoup: {e}", exc_info=True
            )

        return questions

    def _extract_topic_from_message(self, user_message: str) -> str:
        """Extract topic from user message for categorization"""
        # Simple implementation - extract first few meaningful words
        words = user_message.split()
        meaningful_words = [
            w
            for w in words[:5]
            if len(w) > 3 and w.lower() not in ["quiz", "test", "make", "create"]
        ]
        return " ".join(meaningful_words[:3]) if meaningful_words else "General"
