from groq import Groq
import logging
import os
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini at the module level
try:
    FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
    if FLASHCARD_API_KEY:
        genai.configure(api_key=FLASHCARD_API_KEY)
    else:
        logger.warning(
            "FLASHCARD API key for Gemini not found. Vision features will be disabled.")
except Exception as e:
    logger.error(f"Error configuring Gemini: {e}")
    FLASHCARD_API_KEY = None


class AIService:
    """Service for AI interactions used by the agent system"""

    def __init__(self):
        self.client = Groq()
        self.default_model = "gemma2-9b-it"
        # Initialize vision model if API key is available
        if FLASHCARD_API_KEY:
            self.vision_model = genai.GenerativeModel(
                "gemini-1.5-flash-latest")
        else:
            self.vision_model = None

    async def get_ai_response(self, messages, max_tokens=1000, temperature=0.7, model=None, stream=False, image_data=None, image_mime_type=None):
        """Get AI response for agent system - now supports streaming and vision"""
        try:
            # If there's image data, we must use a vision model
            if image_data and image_mime_type and self.vision_model:
                logger.info("Using vision model for multimodal response.")

                # Convert message history to Gemini's format
                gemini_messages = []
                for msg in messages[:-1]:
                    role = 'model' if msg['role'] == 'assistant' else 'user'
                    gemini_messages.append(
                        {'role': role, 'parts': [msg['content']]})

                # Create the multimodal prompt for the last message
                last_message = messages[-1]
                image_part = {'mime_type': image_mime_type, 'data': image_data}
                prompt_parts = [last_message['content'], image_part]
                gemini_messages.append({'role': 'user', 'parts': prompt_parts})

                response = self.vision_model.generate_content(
                    gemini_messages,
                    stream=stream,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature
                    )
                )

                if stream:
                    # For Gemini vision, consume the stream first, then simulate streaming
                    complete_response = ""
                    try:
                        # Consume the streaming response
                        for chunk in response:
                            if chunk.text:
                                complete_response += chunk.text
                    except Exception as e:
                        # Fallback to resolve method if streaming fails
                        logger.warning(
                            f"Stream consumption failed, using resolve: {e}")
                        response.resolve()
                        complete_response = response.text

                    # Create a simple generator that yields the complete response at once
                    class SimpleStreamAdapter:
                        def __init__(self, content):
                            self.content = content
                            self.sent = False

                        def __iter__(self):
                            return self

                        def __next__(self):
                            if not self.sent:
                                self.sent = True
                                mock_choice = type('Choice', (object,), {
                                    'delta': type('Delta', (object,), {'content': self.content})
                                })
                                mock_chunk = type('Chunk', (object,), {
                                    'choices': [mock_choice]
                                })
                                return mock_chunk
                            else:
                                raise StopIteration

                    return SimpleStreamAdapter(complete_response)
                else:
                    # For non-streaming, resolve the response first
                    try:
                        response.resolve()
                        return response.text
                    except Exception as e:
                        # Fallback: consume the response manually
                        logger.warning(
                            f"Direct .text access failed, consuming stream: {e}")
                        complete_response = ""
                        for chunk in response:
                            if chunk.text:
                                complete_response += chunk.text
                        return complete_response

            # Fallback to original Groq logic for text-only
            logger.info("Using default text model for response.")
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

    async def get_ai_response_stream(self, messages, max_tokens=1000, temperature=0.7, model=None, **kwargs):
        """Get streaming AI response for agent system (now passes vision kwargs)"""
        return await self.get_ai_response(messages, max_tokens, temperature, model, stream=True, **kwargs)


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
