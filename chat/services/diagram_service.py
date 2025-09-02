# chat/services/diagram_service.py
import logging
import os
import re
import sys
import time
from typing import Dict, List, Optional

from django.conf import settings

import google.generativeai as genai
import graphviz
from asgiref.sync import sync_to_async

from users.models import CustomUser

from ..config import get_gemini_model
from ..models import Chat, DiagramImage
from ..preference_service import (
    prompt_code_graphviz,
    prompt_description,
    prompt_fix_code,
)
from .interfaces import AICompletionServiceInterface, DiagramServiceInterface

# Configure the generative AI model
FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
genai.configure(api_key=FLASHCARD_API_KEY)
flashcard_model = genai.GenerativeModel(get_gemini_model())


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    return re.sub(r'[<>:"/\\\\|?*]', "_", filename)


def get_system_encoding() -> str:
    """Get the system's preferred encoding, defaulting to UTF-8 if not available."""
    try:
        import locale

        return locale.getpreferredencoding()
    except:
        return "utf-8"


class DiagramService(DiagramServiceInterface):
    """Service for handling diagram generation"""

    def __init__(self, ai_completion_service: AICompletionServiceInterface):
        self.logger = logging.getLogger(__name__)
        self.ai_completion_service = ai_completion_service

    async def generate_diagram_image(
        self,
        chat_history_messages: List[Dict],
        user_query: str,
        chat_id: str,
        user_id: str,
    ) -> Optional[str]:
        """Generate diagram image and return diagram ID"""
        self.logger.info(
            f"Starting diagram generation for chat {chat_id}, user query: {user_query}"
        )

        # Step 1: Generate structured description
        try:
            structured_description_content = flashcard_model.generate_content(
                f"{prompt_description}\n\nGenerate a structured explanation for: {user_query}"
            )
            structured_description_content = structured_description_content.text.strip()

            if (
                not structured_description_content
                or not structured_description_content.strip()
            ):
                self.logger.error("LLM failed to generate a structured description.")
                return None
        except Exception as e:
            self.logger.error(
                f"Error getting structured description from LLM: {e}", exc_info=True
            )
            return None

        # Step 2: Generate Graphviz code
        try:
            graphviz_code_response = flashcard_model.generate_content(
                f"{prompt_code_graphviz}\n\nGenerate a structured explanation for: {structured_description_content}"
            )
            graphviz_code_response = graphviz_code_response.text.strip()

            if not graphviz_code_response or not graphviz_code_response.strip():
                self.logger.error(
                    "LLM failed to generate Graphviz code (empty response)."
                )
                return None
        except Exception as e:
            self.logger.error(
                f"Error getting Graphviz code from LLM: {e}", exc_info=True
            )
            return None

        # Step 3: Clean and process the code
        graphviz_code = self._clean_graphviz_code(graphviz_code_response)

        if not graphviz_code or not (
            "graphviz" in graphviz_code and "Digraph(" in graphviz_code
        ):
            self.logger.error(
                f"Generated Graphviz code does not appear to be valid or is empty."
            )
            return None

        # Step 4: Execute the code and generate image
        try:
            chat_instance = await sync_to_async(Chat.objects.get)(id=chat_id)
            user_instance = await sync_to_async(CustomUser.objects.get)(id=user_id)

            diagram_image_id = await self._render_graphviz(
                graphviz_code,
                chat_instance,
                user_instance,
                user_query,
                structured_description_content,
            )
            return diagram_image_id
        except (Chat.DoesNotExist, CustomUser.DoesNotExist) as e:
            self.logger.error(f"Model instance not found: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error during diagram rendering: {e}", exc_info=True)
            return None

    def _clean_graphviz_code(self, graphviz_code: str) -> str:
        """Clean and prepare Graphviz code for execution"""
        # Extract Python code from markdown block
        python_match = re.search(r"```python\s*\n(.*?)\n```", graphviz_code, re.DOTALL)
        if python_match:
            graphviz_code = python_match.group(1).strip()
        else:
            generic_match = re.search(r"```\s*\n(.*?)\n```", graphviz_code, re.DOTALL)
            if generic_match:
                graphviz_code = generic_match.group(1).strip()
            else:
                # Try to find the start of Python code by 'import graphviz'
                lines = graphviz_code.split("\n")
                actual_code_start_index = -1
                for i, line in enumerate(lines):
                    stripped_line = line.strip()
                    if stripped_line.startswith(
                        "from graphviz import"
                    ) or stripped_line.startswith("import graphviz"):
                        actual_code_start_index = i
                        break

                if actual_code_start_index != -1:
                    graphviz_code = "\n".join(lines[actual_code_start_index:]).strip()

        # Ensure proper imports are present
        if (
            "from graphviz import Digraph" not in graphviz_code
            and "import graphviz" not in graphviz_code
        ):
            graphviz_code = "from graphviz import Digraph\n\n" + graphviz_code

        # Add fallback .render() call if missing
        if ".render(" not in graphviz_code:
            graphviz_code += "\n\n# Fallback render call\ng.render('diagram_output', view=False, cleanup=True)"

        # Fix common Graphviz attribute errors
        graphviz_code = re.sub(r"parent\s*=\s*['\"].*?['\"]", "", graphviz_code)
        graphviz_code = re.sub(r"\.nodes\(\)", ".node()", graphviz_code)
        graphviz_code = re.sub(r"\.nodes\b", ".node", graphviz_code)
        graphviz_code = re.sub(r"\.edges\(\)", ".edge()", graphviz_code)
        graphviz_code = re.sub(r"\.edges\b", ".edge", graphviz_code)

        # Ensure proper Digraph instantiation
        if "Digraph(" in graphviz_code and "format=" not in graphviz_code:
            graphviz_code = re.sub(
                r"Digraph\(\)", "Digraph(format='png')", graphviz_code
            )

        return graphviz_code

    async def _render_graphviz(
        self,
        code_to_execute: str,
        chat_instance,
        user_instance,
        topic_name: str,
        structured_description: str,
    ) -> Optional[str]:
        """Render Graphviz code to image and save to database"""
        current_code = code_to_execute
        local_namespace = {}
        exec_globals = {
            "graphviz": graphviz,
            "Digraph": graphviz.Digraph,
            "os": os,
            "__builtins__": __builtins__,
        }

        # Create temp directory
        debug_dir = os.path.join(settings.MEDIA_ROOT, "temp_diagram_debug")
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time())

        # Set system encoding to UTF-8 for this process
        if sys.platform.startswith("win"):
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")

        for attempt in range(3):
            self.logger.info(f"--- Graphviz Execution Attempt {attempt + 1}/3 ---")

            try:
                # Execute the code
                exec(current_code, exec_globals, local_namespace)

                # Find the graph object
                graph_object = None
                for name, val in local_namespace.items():
                    if isinstance(val, graphviz.Digraph):
                        graph_object = val
                        break

                if not graph_object:
                    self.logger.error("No Digraph object found in the executed code")
                    continue

                # Generate the image
                graph_object.format = "png"
                graph_object.attr("node", fontname="Segoe UI Emoji")
                graph_object.attr("edge", fontname="Segoe UI Emoji")

                try:
                    image_bytes = graph_object.pipe()
                except Exception as pipe_error:
                    self.logger.warning(
                        f"Pipe failed, trying render method: {pipe_error}"
                    )
                    # Fallback to render method
                    temp_filename = f"temp_diagram_{timestamp}_{attempt}"
                    rendered_path = graph_object.render(
                        filename=temp_filename,
                        directory=debug_dir,
                        view=False,
                        cleanup=True,
                    )
                    if rendered_path and os.path.exists(rendered_path):
                        with open(rendered_path, "rb") as f:
                            image_bytes = f.read()
                        os.remove(rendered_path)
                    else:
                        raise Exception("Failed to generate image using render method")

                if not image_bytes:
                    self.logger.error("No image data generated")
                    continue

                # Save to DiagramImage model
                safe_topic_filename = (
                    sanitize_filename(topic_name).replace(" ", "_") + ".png"
                )

                diagram_image_instance = await sync_to_async(
                    DiagramImage.objects.create
                )(
                    chat=chat_instance,
                    user=user_instance,
                    image_data=image_bytes,
                    filename=safe_topic_filename,
                    content_type="image/png",
                )

                self.logger.info(
                    f"✅ Diagram saved successfully with ID: {diagram_image_instance.id}"
                )
                return str(diagram_image_instance.id)

            except Exception as e:
                self.logger.error(f"Error executing code: {str(e)}")

                # Handle common Graphviz errors
                error_str = str(e)
                if "has no attribute 'nodes'" in error_str:
                    current_code = re.sub(r"\.nodes\(\)", ".node()", current_code)
                    current_code = re.sub(r"\.nodes\b", ".node", current_code)
                    continue

                if attempt == 2:  # Last attempt
                    return None

                # Try to get fixed code from AI service
                try:
                    fix_prompt_content = prompt_fix_code.format(
                        topic=topic_name,
                        description=structured_description,
                        erroneous_code=current_code,
                        error_message=str(e),
                    )

                    fixed_code_response = await self.ai_completion_service.get_completion(
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that fixes Python Graphviz code.",
                            },
                            {"role": "user", "content": fix_prompt_content},
                        ],
                        max_tokens=6000,
                        chat_id=str(chat_instance.id),
                        temperature=0.0,
                    )

                    if fixed_code_response and fixed_code_response.strip():
                        current_code = fixed_code_response.strip()
                    else:
                        self.logger.error("No fixed code received from AI service")
                        return None

                except Exception as llm_fix_exc:
                    self.logger.error(f"Error getting fixed code: {str(llm_fix_exc)}")
                    return None

        return None
