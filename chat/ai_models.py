from groq import Groq
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI interactions used by the agent system"""

    def __init__(self):
        self.client = Groq()
        self.default_model = "llama3-8b-8192"

    async def get_ai_response(self, messages, max_tokens=1000, temperature=0.7, model=None, stream=False):
        """Get AI response for agent system - now supports streaming"""
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                return response  # Return the stream object directly
            else:
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AIService error: {e}", exc_info=True)
            raise AIModelException(f"Error getting AI response: {str(e)}")

    async def get_ai_response_stream(self, messages, max_tokens=1000, temperature=0.7, model=None):
        """Get streaming AI response for agent system"""
        return await self.get_ai_response(messages, max_tokens, temperature, model, stream=True)


class AIModelManager:
    def __init__(self):
        self.client = Groq()
        self.default_model = "llama3-8b-8192"
        self.quiz_model = "llama-3.3-70b-versatile"

    def get_chat_completion(self, messages, stream=True, model=None, preferences=None):
        try:
            # Optionally modify messages based on preferences
            if preferences:
                messages.insert(0, {"role": "system", "content": preferences})
            return self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=0.7,
                top_p=1,
                stream=stream,
            )
        except Exception as e:
            raise AIModelException(f"Error getting completion: {str(e)}")

    def generate_quiz(self, prompt):
        try:
            completion = self.get_chat_completion(
                messages=[{"role": "system", "content": prompt}],
                stream=False,
                model=self.quiz_model
            )
            return completion.choices[0].message.content
        except Exception as e:
            raise AIModelException(f"Error generating quiz: {str(e)}")

    def generate_title(self, conversation):
        try:
            title_prompt = f"{conversation}\n\nBased on this conversation, generate a very short title (5 words or less)."
            completion = self.get_chat_completion(
                messages=[{"role": "user", "content": title_prompt}],
                stream=False,
                max_tokens=20
            )
            return completion.choices[0].message.content.strip().strip('"')
        except Exception as e:
            raise AIModelException(f"Error generating title: {str(e)}")


class AIModelException(Exception):
    pass
