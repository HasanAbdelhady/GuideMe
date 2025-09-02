# chat/services/quiz_service.py
import logging
import os
import re
from typing import Any, Dict, List

import google.generativeai as genai
from asgiref.sync import sync_to_async

from ..config import get_gemini_model
from .interfaces import QuizServiceInterface

# Configure the generative AI model
FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
genai.configure(api_key=FLASHCARD_API_KEY)
flashcard_model = genai.GenerativeModel(get_gemini_model())


class QuizService(QuizServiceInterface):
    """Service for handling quiz generation"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def generate_quiz_from_query(
        self,
        chat_history_messages: List[Dict[str, str]],
        user_query: str,
        chat_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate quiz based on user query and conversation history"""
        self.logger.info(
            f"Starting query-focused quiz generation for chat {chat_id} on topic: '{user_query}'"
        )

        # Add the user's specific query to the history
        history_with_query = chat_history_messages + [
            {"role": "user", "content": user_query}
        ]
        content_text = "\n".join(
            [msg["content"] for msg in history_with_query if msg.get("content")]
        )

        if len(content_text) < 100:
            self.logger.warning("Not enough conversation content to generate a quiz.")
            return {"error": "Not enough conversation content to generate a quiz."}

        # Enhanced logic to detect "more" requests and extract the main learning topic
        is_more_request = any(
            word in user_query.lower()
            for word in ["more", "another", "additional", "continue", "keep going"]
        )

        # Extract the main learning topic from conversation
        main_topic = self._extract_main_learning_topic(content_text, user_query)

        if is_more_request and main_topic:
            focus_instruction = f"The user is asking for MORE quizzes on the topic of '{main_topic}'. Create new, different questions about {main_topic} concepts, theories, and practical applications. Do NOT create questions about the conversation itself or what was previously discussed - focus entirely on testing knowledge of {main_topic}."
        else:
            focus_instruction = f"The user has specifically asked to be quizzed on: '{user_query}'. Please create questions that test knowledge and understanding of this topic, focusing on educational content rather than conversation details."

        prompt = f"""
        You are an educational quiz generator that creates questions to test understanding of academic topics.
        {focus_instruction}
        
        IMPORTANT GUIDELINES:
        - Create questions that test understanding of CONCEPTS, THEORIES, and PRACTICAL APPLICATIONS
        - Do NOT create questions about "what the user asked" or "what happened in the conversation"
        - Focus on educational content and knowledge testing
        - Make questions challenging but fair
        - Ensure all 4 options are plausible but only one is correct
        
        Create at least 2 multiple-choice questions (4 options per question).
        For each question, use this HTML structure:
        <div class="quiz-question" data-correct="B">
          <div class="font-semibold mb-1">What is 2+2?</div>
          <form>
            <label><input type="radio" name="q1" value="A"> 3</label><br>
            <label><input type="radio" name="q1" value="B"> 4</label><br>
            <label><input type="radio" name="q1" value="C"> 5</label><br>
            <label><input type="radio" name="q1" value="D"> 6</label><br>
            <button type="submit" class="mt-1.5 px-2 py-1 bg-blue-600 text-white rounded">Check Answer</button>
          </form>
          <div class="quiz-feedback mt-1.5"></div>
        </div>
        Replace the question, answers, and correct value as appropriate.
        **CRITICAL: Output ONLY the HTML for the quiz. Do NOT include any explanations, introductory text, or content outside the HTML structure.**
        
        Educational Context:
        {content_text}
        """

        try:
            quiz_html_response = await sync_to_async(flashcard_model.generate_content)(
                prompt
            )
            quiz_html_text = quiz_html_response.text
            return self._extract_quiz_content(quiz_html_text, user_query)

        except Exception as e:
            self.logger.error(
                f"Query-focused quiz generation call failed: {e}", exc_info=True
            )
            return {"error": f"Quiz generation failed: {str(e)}"}

    async def generate_quiz(
        self, chat_history_messages: List[Dict[str, str]], chat_id: str, **kwargs
    ) -> Dict[str, Any]:
        """Generate general quiz based on conversation history"""
        self.logger.info(f"Starting general quiz generation for chat {chat_id}")

        # Combine conversation history into a single text block
        content_text = "\n".join(
            [msg["content"] for msg in chat_history_messages if msg.get("content")]
        )

        # Ensure there is enough content to generate a meaningful quiz
        if len(content_text) < 200:
            self.logger.warning("Not enough conversation content to generate a quiz.")
            return {"error": "Not enough conversation content to generate a quiz."}

        # Define the prompt for the AI model
        prompt = f"""
        Create at least 2 multiple-choice quizzes (4 options per question) based on the following conversation's relevant scientific information only, related to the learning.
        For each question, use this HTML structure:
        <div class="quiz-question" data-correct="B">
          <div class="font-semibold mb-1">What is 2+2?</div>
          <form>
            <label><input type="radio" name="q1" value="A"> 3</label><br>
            <label><input type="radio" name="q1" value="B"> 4</label><br>
            <label><input type="radio" name="q1" value="C"> 5</label><br>
            <label><input type="radio" name="q1" value="D"> 6</label><br>
            <button type="submit" class="mt-1.5 px-2 py-1 bg-blue-600 text-white rounded">Check Answer</button>
          </form>
          <div class="quiz-feedback mt-1.5"></div>
        </div>
        Replace the question, answers, and correct value as appropriate.
        **CRITICAL: Output ONLY the HTML for the quiz. Do NOT include any explanations, introductory text, or content outside the HTML structure.**
        **Do NOT add phrases like "Here's your quiz" or "Based on the conversation" - output ONLY the quiz HTML.**
        
        Conversation:

        {content_text}
        """

        try:
            quiz_html_response = await sync_to_async(flashcard_model.generate_content)(
                prompt
            )
            quiz_html_text = quiz_html_response.text
            return self._extract_quiz_content(quiz_html_text, "conversation content")

        except Exception as e:
            self.logger.error(f"Quiz generation call failed: {e}", exc_info=True)
            return {"error": f"Quiz generation failed: {str(e)}"}

    def _extract_quiz_content(self, llm_response: str, topic: str) -> Dict[str, Any]:
        """Extract and separate quiz HTML from any accompanying text content"""
        try:
            # Remove any markdown code blocks first
            response_text = llm_response.strip()
            if response_text.startswith("```") and response_text.endswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            # Look for quiz HTML structure
            html_match = re.search(
                r'(<div class="quiz-question".*)', response_text, re.DOTALL
            )

            if html_match:
                # Extract HTML content
                quiz_html = html_match.group(1).strip()

                # Extract any text that appears before the HTML (if any)
                text_before_html = response_text[: html_match.start()].strip()

                # Clean up the HTML to ensure it only contains quiz elements
                quiz_html = self._clean_quiz_html(quiz_html)

                # Prepare result
                result = {"quiz_html": quiz_html}

                # Add any explanatory text to content if it exists and seems meaningful
                if text_before_html and len(text_before_html) > 10:
                    # Filter out common AI-generated prefixes
                    filtered_text = self._filter_ai_prefixes(text_before_html)
                    if filtered_text:
                        result["content"] = filtered_text

                self.logger.info(
                    f"Extracted quiz HTML ({len(quiz_html)} chars) and content ({len(result.get('content', '')) if result.get('content') else 0} chars)"
                )
                return result
            else:
                # No proper HTML structure found
                self.logger.warning(
                    f"Could not find quiz HTML structure in LLM response: {response_text[:200]}..."
                )

                # Check if there's any content that could be salvaged
                if (
                    "quiz" in response_text.lower()
                    or "question" in response_text.lower()
                ):
                    # Try to use the raw response as HTML (fallback)
                    return {
                        "quiz_html": response_text,
                        "content": f"Generated quiz based on {topic}",
                    }
                else:
                    return {"error": "No valid quiz content generated"}

        except Exception as e:
            self.logger.error(f"Error extracting quiz content: {e}", exc_info=True)
            return {"error": f"Failed to process quiz content: {str(e)}"}

    def _clean_quiz_html(self, html_content: str) -> str:
        """Clean the quiz HTML to ensure it only contains quiz-related elements"""
        try:
            # Remove any text that appears after the last </div> tag
            last_div_end = html_content.rfind("</div>")
            if last_div_end != -1:
                # Check if there's significant text after the last </div>
                text_after = html_content[last_div_end + 6 :].strip()
                if text_after and not text_after.startswith("<"):
                    # Remove trailing text that's not HTML
                    html_content = html_content[: last_div_end + 6]

            # Remove any leading text that's not HTML
            first_div_start = html_content.find("<div")
            if first_div_start > 0:
                leading_text = html_content[:first_div_start].strip()
                if leading_text and not leading_text.startswith("<"):
                    # Remove leading text that's not HTML
                    html_content = html_content[first_div_start:]

            return html_content.strip()

        except Exception as e:
            self.logger.error(f"Error cleaning quiz HTML: {e}")
            return html_content

    def _filter_ai_prefixes(self, text: str) -> str:
        """Filter out common AI-generated prefixes and return meaningful content"""
        # Common AI-generated prefixes to remove
        ai_prefixes = [
            "here's your quiz",
            "here is your quiz",
            "based on the conversation",
            "quiz:",
            "here are the questions",
            "below is the quiz",
            "i've created a quiz",
            "the quiz is ready",
        ]

        text_lower = text.lower().strip()

        # Remove common prefixes
        for prefix in ai_prefixes:
            if text_lower.startswith(prefix):
                return ""  # Return empty string for these common prefixes

        # If text is very short or seems like a prefix, ignore it
        if len(text) < 15 or any(
            phrase in text_lower for phrase in ["here's", "here is", "below"]
        ):
            return ""

        return text.strip()

    def _extract_main_learning_topic(self, content_text: str, user_query: str) -> str:
        """Extract the main learning topic from conversation content and user queries"""
        # Common academic subjects and topics
        academic_topics = [
            "machine learning",
            "deep learning",
            "artificial intelligence",
            "ai",
            "neural networks",
            "data science",
            "python",
            "javascript",
            "programming",
            "algorithms",
            "data structures",
            "computer science",
            "mathematics",
            "statistics",
            "calculus",
            "linear algebra",
            "physics",
            "chemistry",
            "biology",
            "economics",
            "finance",
            "marketing",
            "business",
            "cybersecurity",
            "networking",
            "databases",
            "web development",
            "software engineering",
            "cloud computing",
            "blockchain",
        ]

        # Look for quiz-related phrases to find the topic
        quiz_patterns = [
            r"quiz\s+(?:me\s+)?(?:on\s+)?([a-zA-Z\s]+?)(?:\.|$|quiz|test)",
            r"test\s+(?:my\s+)?(?:knowledge\s+)?(?:of\s+)?([a-zA-Z\s]+?)(?:\.|$|quiz|test)",
            r"questions?\s+(?:about\s+)?([a-zA-Z\s]+?)(?:\.|$|quiz|test)",
        ]

        # First try to extract from recent conversation
        recent_content = (
            content_text[-1000:] if len(content_text) > 1000 else content_text
        )
        combined_text = recent_content.lower() + " " + user_query.lower()

        # Try pattern matching first
        for pattern in quiz_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) > 2 and match not in ["me", "my", "the", "and", "or"]:
                    return match

        # Look for academic topics mentioned in the conversation
        for topic in academic_topics:
            if topic in combined_text:
                return topic

        # Extract meaningful words from user query (fallback)
        words = user_query.lower().split()
        meaningful_words = [
            w
            for w in words
            if len(w) > 3
            and w
            not in [
                "quiz",
                "test",
                "more",
                "make",
                "create",
                "give",
                "another",
                "additional",
            ]
        ]

        if meaningful_words:
            return " ".join(meaningful_words[:2])

        # Ultimate fallback - try to find any capitalized terms that might be topics
        capitalized_terms = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", content_text)
        if capitalized_terms:
            return capitalized_terms[-1]  # Take the most recent one

        return "the subject"
