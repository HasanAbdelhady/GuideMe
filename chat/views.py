# chat/views.py
import asyncio
import html
import io
import json
import logging
import os
import re
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import close_old_connections
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView

import google.generativeai as genai
from asgiref.sync import async_to_sync, sync_to_async
from groq import APIStatusError, Groq
from pydantic import BaseModel

from .agent_system import ChatAgentSystem
from .ai_models import AIService
from .models import (
    Chat,
    ChatRAGFile,
    ChatVectorIndex,
    DiagramImage,
    DocumentChunk,
    Message,
)
from .preference_service import PreferenceService
from .rag import RAG_pipeline
from .services import ChatService

chat_service = ChatService()
ai_service = AIService()
agent_system = ChatAgentSystem(chat_service, ai_service)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

groq_client = Groq()

# get your api key from https://aistudio.google.com/apikey
FLASHCARD_API_KEY = os.environ.get("FLASHCARD")

# Configure the generative AI model for flashcards
genai.configure(api_key=FLASHCARD_API_KEY)
flashcard_model = genai.GenerativeModel("gemini-2.5-flash")


def custom_404_view(request, exception):
    return redirect("new_chat")


@method_decorator(login_required, name="dispatch")
class ChatView(View):
    template_name = "chat/chat.html"

    def get(self, request, chat_id=None):
        # Handle AJAX requests for message updates
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" and chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
                messages = list(
                    chat.messages.all().order_by("created_at").values("role", "content")
                )
                return JsonResponse({"messages": messages})
            except Chat.DoesNotExist:
                return JsonResponse({"error": "Chat not found"}, status=404)

        chats = Chat.objects.filter(user=request.user).order_by("-updated_at")
        is_new_chat = request.path == "/chat/new/"

        # Handle new chat
        if is_new_chat:
            temp_id = f"temp_{int(time.time())}"
            return render(
                request,
                self.template_name,
                {
                    "current_chat": {"id": temp_id, "title": "New Chat"},
                    "conversation": [],
                    "chats": chats,
                    "is_new_chat": True,
                },
            )

        # Handle existing chat
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
                db_messages = chat.messages.all().order_by(
                    "created_at"
                )  # Renamed to db_messages
                conversation = []
                for msg_obj in db_messages:  # Iterate over actual model instances
                    msg_dict = {
                        "role": msg_obj.role,
                        "id": msg_obj.id,
                        "type": msg_obj.type,
                        "created_at": msg_obj.created_at.isoformat(),
                        "is_edited": msg_obj.is_edited,
                        "edited_at": (
                            msg_obj.edited_at.isoformat() if msg_obj.edited_at else None
                        ),
                        "text": None,  # Default to None
                        # Default to None (used for quiz HTML by current template)
                        "html": None,
                        "diagram_image_url": None,  # Initialize diagram_image_url
                        "diagram_image_id_for_template": None,  # ADD THIS
                        "structured_content": None,
                        "is_mixed_content": (
                            msg_obj.is_mixed_content()
                            if hasattr(msg_obj, "is_mixed_content")
                            else False
                        ),  # New field
                        "mixed_content_data": None,  # Mixed content structure
                    }

                    # Handle different message types properly
                    if msg_obj.type == "mixed":
                        # This is a mixed content message - handle all components
                        msg_dict["text"] = msg_obj.content
                        # Only YouTube data
                        msg_dict["structured_content"] = msg_obj.structured_content
                        # Mixed content structure
                        msg_dict["mixed_content_data"] = msg_obj.mixed_content_data

                        # Set individual flags for frontend rendering
                        if (
                            hasattr(msg_obj, "has_diagram")
                            and msg_obj.has_diagram
                            and msg_obj.diagram_image_id
                        ):
                            msg_dict["diagram_image_url"] = (
                                f"/chat/diagram_image/{msg_obj.diagram_image_id}/"
                            )
                            msg_dict["diagram_image_id_for_template"] = str(
                                msg_obj.diagram_image_id
                            )

                        if (
                            hasattr(msg_obj, "has_quiz")
                            and msg_obj.has_quiz
                            and msg_obj.quiz_html
                        ):
                            msg_dict["html"] = msg_obj.quiz_html

                        logger.info(
                            f"Loaded mixed content message with components: {msg_dict['mixed_content_data']}"
                        )

                    elif msg_obj.type == "diagram" and msg_obj.diagram_image_id:
                        # This is a diagram message
                        # Construct URL to the new serving view
                        msg_dict["diagram_image_url"] = (
                            f"/chat/diagram_image/{msg_obj.diagram_image_id}/"
                        )
                        # Use the content as description text
                        msg_dict["text"] = msg_obj.content
                        msg_dict["diagram_image_id_for_template"] = str(
                            msg_obj.diagram_image_id
                        )  # ADD THIS
                        logger.info(
                            f"Loaded diagram message. URL: {msg_dict['diagram_image_url']}, ID for template: {msg_dict['diagram_image_id_for_template']}"
                        )
                        logger.info(
                            f"[ChatView.get] Preparing diagram msg_dict: {msg_dict}"
                        )
                    elif msg_obj.type == "youtube":
                        msg_dict["text"] = msg_obj.content
                        msg_dict["structured_content"] = msg_obj.structured_content
                    else:
                        # Default handler for text, and the base for quizzes
                        msg_dict["text"] = msg_obj.content
                        # If it's a quiz, also add the HTML
                        if msg_obj.type == "quiz" and msg_obj.quiz_html:
                            msg_dict["html"] = msg_obj.quiz_html

                    conversation.append(msg_dict)

                return render(
                    request,
                    self.template_name,
                    {
                        "current_chat": chat,
                        "conversation": conversation,
                        "chats": chats,
                        "is_new_chat": False,
                        "MEDIA_URL": settings.MEDIA_URL,  # Add MEDIA_URL to the context
                    },
                )
            except Chat.DoesNotExist:
                return redirect("new_chat")

        # Default to chat list or new chat
        return redirect("new_chat")


# @method_decorator(login_required, name='dispatch') # Ensure this is commented out
class ChatStreamView(View):
    async def post(self, request, chat_id):
        try:
            user = await request.auser()
            if not user.is_authenticated:
                return JsonResponse({"error": "Authentication required"}, status=401)

            logger.info(
                f"ChatStreamView.post called for chat_id={chat_id} by user {user.id}"
            )

            # Use the pre-loaded 'user' object for DB queries
            try:
                chat = await sync_to_async(Chat.objects.select_related("user").get)(
                    id=chat_id, user=user
                )
            except Chat.DoesNotExist:
                logger.error(f"Chat with id={chat_id} not found for user {user.id}.")
                # This should be an async-safe way to raise Http404, but for simplicity
                # we return a JsonResponse which is clear for an API view.
                return JsonResponse({"error": "Chat not found."}, status=404)

            logger.info(f"Got chat: {chat} with pre-fetched user: {chat.user}")

            user_typed_prompt = request.POST.get("prompt", "").strip()
            logger.info(f"User typed prompt: {user_typed_prompt}")

            uploaded_file = request.FILES.get("file")
            logger.info(f"Uploaded file: {uploaded_file}")

            # New: Handle image file for vision model
            image_file = request.FILES.get("image_file")
            image_data_for_llm = None
            image_mime_type_for_llm = None
            if image_file:
                logger.info(f"Image file uploaded: {image_file.name}")
                # Ensure it's a valid image type
                allowed_image_types = [
                    "image/jpeg",
                    "image/png",
                    "image/gif",
                    "image/webp",
                ]
                if image_file.content_type in allowed_image_types:
                    image_data_for_llm = image_file.read()
                    image_mime_type_for_llm = image_file.content_type
                    logger.info(
                        f"Image data prepared for LLM: {len(image_data_for_llm)} bytes, MIME type: {image_mime_type_for_llm}"
                    )
                else:
                    logger.warning(f"Unsupported image type: {image_file.content_type}")
                    # Optionally, send a notification back to the user
                    # For now, we'll just log it and proceed without the image.

            file_info_for_llm = None
            prompt_for_display_and_db = user_typed_prompt
            llm_query_content = user_typed_prompt

            if uploaded_file:
                file_info_for_llm = chat_service.extract_text_from_uploaded_file(
                    uploaded_file
                )
                llm_query_content = (
                    f"{user_typed_prompt}\n\n"
                    f"Here is the complete text content extracted from the uploaded file '{file_info_for_llm['filename']}':\n\n"
                    f"--- START OF FILE CONTENT ---\n"
                    f"{file_info_for_llm['text_content']}\n"
                    f"--- END OF FILE CONTENT ---\n\n"
                    f"Please analyze this content and answer the question above."
                    if user_typed_prompt
                    else f"Here is the complete text content extracted from the uploaded file '{file_info_for_llm['filename']}':\n\n"
                    f"--- START OF FILE CONTENT ---\n"
                    f"{file_info_for_llm['text_content']}\n"
                    f"--- END OF FILE CONTENT ---\n\n"
                    f"Please analyze and summarize this content."
                )
                logger.info(
                    f"LLM query content augmented with file text from: {file_info_for_llm['filename']}"
                )
                if file_info_for_llm["was_truncated"]:
                    logger.info(
                        f"File {file_info_for_llm['filename']} was truncated. Original: {file_info_for_llm['original_char_count']} chars, Final: {file_info_for_llm['final_char_count']} chars."
                    )

            rag_mode_active_str = request.POST.get("rag_mode_active", "false")
            rag_mode_active = rag_mode_active_str.lower() == "true"

            diagram_mode_active_str = request.POST.get(
                "diagram_mode_active", "false"
            )  # Get diagram_mode_active
            diagram_mode_active = diagram_mode_active_str.lower() == "true"
            logger.info(f"Diagram mode active: {diagram_mode_active}")

            youtube_mode_active_str = request.POST.get("youtube_mode_active", "false")
            youtube_mode_active = youtube_mode_active_str.lower() == "true"
            logger.info(f"YouTube mode active: {youtube_mode_active}")

            # RAG indexing is now handled in ChatRAGFilesView when files are uploaded

            # Diagram mode takes precedence if active
            if diagram_mode_active:
                logger.info(
                    "Diagram mode is ACTIVE. RAG mode will be ignored for this turn if it was also active."
                )
                rag_mode_active = (
                    False  # Ensure RAG is off if diagram is on for this turn
                )

            if youtube_mode_active:
                logger.info(
                    "YouTube mode is ACTIVE. RAG and Diagram modes will be ignored for this turn."
                )
                rag_mode_active = False
                diagram_mode_active = False

            is_reprompt_after_edit = (
                request.POST.get("is_reprompt_after_edit") == "true"
            )

            current_message_count = await sync_to_async(chat.messages.count)()
            is_handling_continuation_of_new_chat = (
                current_message_count == 1
                and (await sync_to_async(lambda: chat.messages.first().content)())
                == user_typed_prompt
            )

            if not is_handling_continuation_of_new_chat and not is_reprompt_after_edit:
                logger.info(
                    "User message will be saved in stream_response upon successful LLM interaction."
                )
            elif is_reprompt_after_edit:
                logger.info(
                    "Skipping user message save as this is a re-prompt after an edit (no new user message to save)."
                )
            else:
                logger.info(
                    "Skipping user message save in ChatStreamView as create_chat already handled the initial user message."
                )

            if (
                chat.title == "New Chat"
                and user_typed_prompt
                and not is_reprompt_after_edit
            ):
                await sync_to_async(chat_service.update_chat_title)(
                    chat, user_typed_prompt
                )
                logger.info("Chat title updated.")

            system_prompt_text = await sync_to_async(
                PreferenceService.get_system_prompt
            )(user)
            messages_for_llm = [{"role": "system", "content": system_prompt_text}]

            chat_history_db = await sync_to_async(chat_service.get_chat_history)(chat)

            if is_handling_continuation_of_new_chat:
                logger.info(
                    "First turn of new chat: LLM history will start with system prompt, current query will be added next."
                )
            else:
                # For diagram generation, we might want the full history for context.
                # For regular chat, it's already limited by get_chat_history.
                for msg_data in chat_history_db:
                    # Don't include previous diagram placeholder texts or image URLs in LLM history for new diagram
                    if diagram_mode_active and msg_data.type == "diagram":
                        if msg_data.content and not msg_data.content.startswith(
                            "[Diagram generated"
                        ):
                            messages_for_llm.append(
                                {"role": msg_data.role, "content": msg_data.content}
                            )
                        # else skip diagram placeholders for new diagram generation context
                    else:
                        messages_for_llm.append(
                            {"role": msg_data.role, "content": msg_data.content}
                        )

                logger.info(
                    f"Ongoing chat or re-prompt: Added {len(messages_for_llm) - 1} messages from DB to LLM context (excluding system prompt)."
                )

            # Add the current user query that might be for a diagram or regular chat
            # llm_query_content already contains augmented file text if any
            messages_for_llm.append({"role": "user", "content": llm_query_content})

            logger.info(
                f"Message history prepared with {len(messages_for_llm)} messages for LLM. Last user message for LLM: {llm_query_content[:200]}..."
            )

            current_message_count_final = await sync_to_async(chat.messages.count)()
            is_new_chat_bool = current_message_count_final <= 1

            return await self.stream_response(
                chat=chat,
                messages_for_llm=messages_for_llm,
                query_for_rag=user_typed_prompt if rag_mode_active else None,
                is_new_chat=is_new_chat_bool,
                current_user_prompt_for_saving=(
                    user_typed_prompt
                    if not (
                        is_handling_continuation_of_new_chat or is_reprompt_after_edit
                    )
                    else None
                ),
                attached_file_name_for_rag=None,  # RAG files are now managed separately
                file_info_for_truncation_warning=file_info_for_llm,
                diagram_mode_active=diagram_mode_active,  # Pass diagram_mode_active
                # Pass user_id for diagram path
                user_id_for_diagram=user.id if diagram_mode_active else None,
                youtube_mode_active=youtube_mode_active,
                query_for_youtube_agent=(
                    user_typed_prompt if youtube_mode_active else None
                ),
                rag_mode_active=rag_mode_active,  # Add this parameter
                # New: Pass image data to the streaming response
                image_data=image_data_for_llm,
                image_mime_type=image_mime_type_for_llm,
            )

        except Exception as e:
            logger.error(f"Exception in ChatStreamView.post: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    async def stream_response(
        self,
        chat,
        messages_for_llm,
        query_for_rag=None,
        is_new_chat=False,
        current_user_prompt_for_saving=None,
        attached_file_name_for_rag=None,
        file_info_for_truncation_warning=None,
        diagram_mode_active=False,
        user_id_for_diagram=None,
        youtube_mode_active=False,
        query_for_youtube_agent=None,
        rag_mode_active=False,
        image_data=None,
        image_mime_type=None,
    ):
        async def event_stream_async():
            user_message_saved = False
            try:
                logger.info("stream_response.event_stream_async started.")

                if (
                    file_info_for_truncation_warning
                    and file_info_for_truncation_warning["was_truncated"]
                ):
                    warning_msg = (
                        f"The content of '{file_info_for_truncation_warning['filename']}' was truncated "
                        f"(from {file_info_for_truncation_warning['original_char_count']} to {file_info_for_truncation_warning['final_char_count']} characters) "
                        f"because it was too long for direct processing with your message. "
                        f"For full document analysis, please use the 'Manage RAG Context' feature."
                    )
                    logger.info(f"Sending truncation warning to client: {warning_msg}")
                    yield f"data: {json.dumps({'type': 'file_info', 'status': 'truncated', 'message': warning_msg})}\n\n"

                max_tokens_for_llm = 7000
                logger.info(
                    f"[ChatStreamView.stream_response] Max tokens for LLM: {max_tokens_for_llm}"
                )

                if not user_message_saved and current_user_prompt_for_saving:
                    await sync_to_async(close_old_connections)()
                    await sync_to_async(Message.objects.create)(
                        chat=chat, role="user", content=current_user_prompt_for_saving
                    )
                    user_message_saved = True
                    logger.info(
                        f"User message '{current_user_prompt_for_saving[:50]}...' saved (Normal stream mode)."
                    )

                # --- Mode-based routing: RAG vs Agent ---
                if rag_mode_active:
                    # RAG mode is on, stream directly from documents
                    logger.info(
                        "RAG mode is active. Bypassing agent and calling stream_completion directly."
                    )
                    stream = await chat_service.stream_completion(
                        messages=messages_for_llm,
                        query=query_for_rag,
                        max_tokens=max_tokens_for_llm,
                        chat_id=chat.id,
                        is_new_chat=is_new_chat,
                        attached_file_name=attached_file_name_for_rag,
                    )

                    logger.info(
                        "Got stream from chat_service.stream_completion (RAG mode)."
                    )
                    accumulated_response_for_db = ""  # For DB saving
                    frontend_buffer = ""  # Buffer for sending to frontend
                    BUFFER_LENGTH_THRESHOLD_CHARS = (
                        25  # Reduced from 50 for better streaming
                    )

                    for chunk in stream:
                        content = getattr(chunk.choices[0].delta, "content", None)
                        if content:
                            accumulated_response_for_db += content
                            frontend_buffer += content

                            # Send smaller chunks more frequently for better streaming experience
                            if ("\n" in frontend_buffer) or (
                                len(frontend_buffer) >= BUFFER_LENGTH_THRESHOLD_CHARS
                            ):
                                yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"
                                frontend_buffer = ""  # Reset buffer

                    if frontend_buffer:
                        yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"

                    if accumulated_response_for_db:
                        await sync_to_async(close_old_connections)()
                        await sync_to_async(Message.objects.create)(
                            chat=chat,
                            role="assistant",
                            content=accumulated_response_for_db,
                        )
                        logger.info(
                            "Assistant message created from accumulated RAG stream."
                        )

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                    # if files_rag_instance:
                    #     rag_stats = {
                    #         "file_chunks_used": (
                    #             len(files_rag_instance.chunks)
                    #             if files_rag_instance
                    #             and hasattr(files_rag_instance, "chunks")
                    #             else 0
                    #         ),
                    #     }
                    #     yield f"data: {json.dumps({'type': 'metadata', 'content': rag_stats})}\n\n"
                    # return  # End stream for RAG mode

                # --- Agent System Integration (if not in RAG mode) ---
                logger.info("RAG mode is inactive. Using agent system.")
                user = await sync_to_async(lambda: chat.user)()
                chat_context = {
                    "chat": chat,
                    "user": user,
                    "messages_for_llm": messages_for_llm[:-1],
                    "chat_service": chat_service,
                    # New: Add image data to chat context if available
                    "image_data": image_data,
                    "image_mime_type": image_mime_type,
                }

                active_modes = {
                    "rag": rag_mode_active,
                    "diagram": diagram_mode_active,
                    "youtube": youtube_mode_active,
                }

                user_message = (
                    current_user_prompt_for_saving
                    if current_user_prompt_for_saving
                    else messages_for_llm[-1]["content"]
                )

                ai_response, tool_results = await agent_system.process_message(
                    user_message=user_message,
                    chat_context=chat_context,
                    active_modes=active_modes,
                )

                # Separate successful tool results from background processes
                primary_tools_used = [
                    r
                    for r in tool_results
                    if r.message_type not in ["background_process"] and r.success
                ]
                background_results = [
                    r for r in tool_results if r.message_type == "background_process"
                ]

                # Handle background processes (notifications)
                for background_result in background_results:
                    if background_result.content:
                        yield f"data: {json.dumps({'type': 'notification', 'content': background_result.content})}\n\n"

                # Check if we need to stream AI responses for better UX
                needs_streaming = len(primary_tools_used) == 0 or (
                    len(primary_tools_used) == 1
                    and any(
                        keyword in user_message.lower()
                        for keyword in [
                            "explain",
                            "what is",
                            "how does",
                            "why",
                            "tell me about",
                        ]
                    )
                )

                # If we have multiple tool results, combine them into a single mixed-content message
                if len(primary_tools_used) > 1:
                    # Signal the start of mixed content to frontend
                    yield f"data: {json.dumps({'type': 'mixed_content_start'})}\n\n"

                    await self._handle_mixed_content_message(
                        chat, primary_tools_used, ai_response
                    )

                    # Stream all the tool results to frontend in the order they were requested by the user
                    # Note: primary_tools_used is now sorted by execution_order from the agent system
                    logger.info(
                        f"Streaming {len(primary_tools_used)} tool results in requested order"
                    )
                    for i, tool_result in enumerate(primary_tools_used):
                        logger.info(
                            f"Streaming tool result {i + 1}: {tool_result.message_type} (order: {getattr(tool_result, 'execution_order', 'unknown')})"
                        )

                        if tool_result.message_type == "diagram":
                            diagram_image_id = tool_result.structured_data.get(
                                "diagram_image_id"
                            )
                            if diagram_image_id:
                                yield f"data: {json.dumps({'type': 'diagram_image', 'diagram_image_id': str(diagram_image_id), 'text_content': tool_result.content, 'order': getattr(tool_result, 'execution_order', i)})}\n\n"

                        elif tool_result.message_type == "youtube":
                            if (
                                tool_result.structured_data
                                and "videos" in tool_result.structured_data
                            ):
                                video_list = tool_result.structured_data.get(
                                    "videos", []
                                )
                                yield f"data: {json.dumps({'type': 'youtube_recommendations', 'data': video_list, 'order': getattr(tool_result, 'execution_order', i)})}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'content', 'content': tool_result.content, 'order': getattr(tool_result, 'execution_order', i)})}\n\n"

                        elif tool_result.message_type == "quiz":
                            quiz_html = tool_result.structured_data.get("quiz_html", "")
                            # For mixed content, we'll include the quiz HTML directly in the stream
                            yield f"data: {json.dumps({'type': 'quiz_html', 'quiz_html': quiz_html, 'order': getattr(tool_result, 'execution_order', i)})}\n\n"

                    # Stream the AI response if present
                    if ai_response:
                        # Check if AI response is a stream object or string
                        # Groq Stream objects have __iter__ method but not 'choices' attribute directly
                        is_stream = (
                            hasattr(ai_response, "__iter__")
                            and hasattr(ai_response, "__next__")
                            and not isinstance(ai_response, str)
                        )

                        if is_stream:  # It's a stream object
                            accumulated_ai_response = ""
                            frontend_buffer = ""
                            BUFFER_THRESHOLD = 15  # Smaller buffer for better streaming

                            for chunk in ai_response:
                                content = getattr(
                                    chunk.choices[0].delta, "content", None
                                )
                                if content:
                                    accumulated_ai_response += content
                                    frontend_buffer += content

                                    if (
                                        len(frontend_buffer) >= BUFFER_THRESHOLD
                                        or "\n" in frontend_buffer
                                    ):
                                        yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"
                                        frontend_buffer = ""

                            # Send any remaining content
                            if frontend_buffer:
                                yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"

                            # Save the final AI response to database
                            if accumulated_ai_response:
                                await sync_to_async(close_old_connections)()
                                await sync_to_async(Message.objects.create)(
                                    chat=chat,
                                    role="assistant",
                                    content=accumulated_ai_response,
                                )
                        else:
                            # It's a regular string response
                            await sync_to_async(close_old_connections)()
                            await sync_to_async(Message.objects.create)(
                                chat=chat, role="assistant", content=ai_response
                            )
                            yield f"data: {json.dumps({'type': 'content', 'content': ai_response})}\n\n"

                # Handle single tool result (maintain existing behavior for backwards compatibility)
                elif len(primary_tools_used) == 1:
                    tool_result = primary_tools_used[0]

                    if tool_result.message_type == "diagram":
                        diagram_image_id = tool_result.structured_data.get(
                            "diagram_image_id"
                        )
                        if diagram_image_id:
                            await sync_to_async(close_old_connections)()
                            new_diagram_message = await sync_to_async(
                                Message.objects.create
                            )(
                                chat=chat,
                                role="assistant",
                                content=tool_result.content,
                                type="diagram",
                                diagram_image_id=diagram_image_id,
                            )
                            yield f"""data: {
                                json.dumps(
                                    {
                                        "type": "diagram_image",
                                        "diagram_image_id": str(diagram_image_id),
                                        "message_id": new_diagram_message.id,
                                        "text_content": tool_result.content,
                                    }
                                )
                            }\n\n"""

                    elif tool_result.message_type == "youtube":
                        if (
                            tool_result.structured_data
                            and "videos" in tool_result.structured_data
                        ):
                            video_list = tool_result.structured_data.get("videos", [])
                            await sync_to_async(close_old_connections)()
                            await sync_to_async(Message.objects.create)(
                                chat=chat,
                                role="assistant",
                                content=tool_result.content,
                                type="youtube",
                                structured_content=video_list,
                            )
                            yield f"data: {json.dumps({'type': 'youtube_recommendations', 'data': video_list})}\n\n"
                        else:
                            await sync_to_async(close_old_connections)()
                            await sync_to_async(Message.objects.create)(
                                chat=chat,
                                role="assistant",
                                content=tool_result.content,
                                type="text",
                            )
                            yield f"data: {json.dumps({'type': 'content', 'content': tool_result.content})}\n\n"

                    elif tool_result.message_type == "quiz":
                        quiz_html = tool_result.structured_data.get("quiz_html", "")
                        await sync_to_async(close_old_connections)()
                        new_quiz_message = await sync_to_async(Message.objects.create)(
                            chat=chat,
                            role="assistant",
                            content=tool_result.content,
                            type="quiz",
                            quiz_html=quiz_html,
                        )
                        yield f"data: {json.dumps({'type': 'trigger_quiz_render', 'message_id': new_quiz_message.id})}\n\n"

                    # Handle AI response for single tool case
                    if ai_response:
                        # Check if AI response is a stream object or string
                        # Groq Stream objects have __iter__ method but not 'choices' attribute directly
                        is_stream = (
                            hasattr(ai_response, "__iter__")
                            and hasattr(ai_response, "__next__")
                            and not isinstance(ai_response, str)
                        )

                        if is_stream:  # It's a stream object
                            accumulated_ai_response = ""
                            frontend_buffer = ""
                            BUFFER_THRESHOLD = 15  # Smaller buffer for better streaming

                            for chunk in ai_response:
                                content = getattr(
                                    chunk.choices[0].delta, "content", None
                                )
                                if content:
                                    accumulated_ai_response += content
                                    frontend_buffer += content

                                    if (
                                        len(frontend_buffer) >= BUFFER_THRESHOLD
                                        or "\n" in frontend_buffer
                                    ):
                                        yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"
                                        frontend_buffer = ""

                            # Send any remaining content
                            if frontend_buffer:
                                yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"

                            # Save the final AI response to database
                            if accumulated_ai_response:
                                await sync_to_async(close_old_connections)()
                                await sync_to_async(Message.objects.create)(
                                    chat=chat,
                                    role="assistant",
                                    content=accumulated_ai_response,
                                )
                        else:
                            # It's a regular string response
                            await sync_to_async(close_old_connections)()
                            await sync_to_async(Message.objects.create)(
                                chat=chat, role="assistant", content=ai_response
                            )
                            yield f"data: {json.dumps({'type': 'content', 'content': ai_response})}\n\n"

                # Handle case with no tools used but AI response
                elif ai_response:
                    # Check if AI response is a stream object or string
                    # Groq Stream objects have __iter__ method but not 'choices' attribute directly
                    is_stream = (
                        hasattr(ai_response, "__iter__")
                        and hasattr(ai_response, "__next__")
                        and not isinstance(ai_response, str)
                    )

                    if is_stream:  # It's a stream object
                        accumulated_ai_response = ""
                        frontend_buffer = ""
                        BUFFER_THRESHOLD = 15  # Smaller buffer for better streaming

                        for chunk in ai_response:
                            content = getattr(chunk.choices[0].delta, "content", None)
                            if content:
                                accumulated_ai_response += content
                                frontend_buffer += content

                                if (
                                    len(frontend_buffer) >= BUFFER_THRESHOLD
                                    or "\n" in frontend_buffer
                                ):
                                    yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"
                                    frontend_buffer = ""

                        # Send any remaining content
                        if frontend_buffer:
                            yield f"data: {json.dumps({'type': 'content', 'content': frontend_buffer})}\n\n"

                        # Save the final AI response to database
                        if accumulated_ai_response:
                            await sync_to_async(close_old_connections)()
                            await sync_to_async(Message.objects.create)(
                                chat=chat,
                                role="assistant",
                                content=accumulated_ai_response,
                            )
                    else:
                        # It's a regular string response
                        await sync_to_async(close_old_connections)()
                        await sync_to_async(Message.objects.create)(
                            chat=chat, role="assistant", content=ai_response
                        )
                        yield f"data: {json.dumps({'type': 'content', 'content': ai_response})}\n\n"

                # Send done signal
                if primary_tools_used or ai_response:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                # Fallback for if agent system fails silently
                yield f"data: {json.dumps({'type': 'done', 'message': 'No action taken.'})}\n\n"

            except APIStatusError as e:
                logger.error(
                    f"Groq APIStatusError in stream_response.event_stream_async: Status {e.status_code}, Response: {e.response.text if e.response else 'No response body'}",
                    exc_info=True,
                )
                user_message = "An API error occurred with the language model."
                if e.status_code == 413:
                    try:
                        error_detail = e.response.json()
                        if error_detail.get("error", {}).get(
                            "type"
                        ) == "tokens" or "tokens per minute (TPM)" in error_detail.get(
                            "error", {}
                        ).get(
                            "message", ""
                        ):
                            user_message = "The request is too large for the model. Please try reducing your message size or shortening the conversation if the history is very long."
                    except json.JSONDecodeError:
                        if "Request too large" in str(
                            e
                        ) or "tokens per minute (TPM)" in str(e):
                            user_message = "The request is too large for the model. Please try reducing your message size or shortening the conversation if the history is very long."

                yield f"data: {json.dumps({'type': 'error', 'content': user_message})}\n\n"

            except Exception as e:
                logger.error(
                    f"Generic exception in stream_response.event_stream_async: {str(e)}",
                    exc_info=True,
                )
                yield f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"
            finally:
                logger.info("stream_response.event_stream_async has finished.")
                # Ensure the 'done' event is always sent to the client
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # The sync wrapper is unnecessary with modern async Django and can cause issues.
        # We pass the async generator directly to StreamingHttpResponse.
        response = StreamingHttpResponse(
            event_stream_async(), content_type="text/event-stream"
        )
        # Add headers to prevent caching by intermediaries
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        logger.info("StreamingHttpResponse returned.")
        return response

    async def _handle_mixed_content_message(self, chat, tool_results, ai_response):
        """Create a single message that combines multiple tool results with mixed content"""
        try:
            # Create mixed content structure for frontend rendering
            mixed_content_structure = {"type": "mixed", "components": []}

            # Set flags for different content types
            has_diagram = False
            has_youtube = False
            has_quiz = False
            has_code = False
            diagram_image_id = None
            quiz_html = ""
            youtube_videos = None  # Keep YouTube data separate

            # Process each tool result in the order they were requested
            for tool_result in tool_results:
                component = {
                    "type": tool_result.message_type,
                    "content": tool_result.content,
                    # Fallback order
                    "order": getattr(
                        tool_result,
                        "execution_order",
                        len(mixed_content_structure["components"]),
                    ),
                }

                if tool_result.message_type == "diagram":
                    has_diagram = True
                    diagram_image_id = tool_result.structured_data.get(
                        "diagram_image_id"
                    )
                    component["diagram_image_id"] = (
                        str(diagram_image_id) if diagram_image_id else None
                    )

                elif tool_result.message_type == "youtube":
                    has_youtube = True
                    if (
                        tool_result.structured_data
                        and "videos" in tool_result.structured_data
                    ):
                        youtube_videos = tool_result.structured_data.get("videos", [])
                        component["videos"] = youtube_videos

                elif tool_result.message_type == "quiz":
                    has_quiz = True
                    quiz_html = tool_result.structured_data.get("quiz_html", "")
                    component["quiz_html"] = quiz_html

                # Check if content contains code (simple heuristic)
                if any(
                    keyword in tool_result.content.lower()
                    for keyword in ["def ", "function", "import ", "class ", "```"]
                ):
                    has_code = True

                mixed_content_structure["components"].append(component)

            # Add AI response if present (this will be the brief contextual message)
            if ai_response:
                mixed_content_structure["ai_response"] = ai_response

            # Use the AI response as the main content (brief message)
            # Frontend will render the actual tool results separately
            message_content = (
                ai_response if ai_response else "Here are your requested resources:"
            )

            await sync_to_async(close_old_connections)()
            await sync_to_async(Message.objects.create)(
                chat=chat,
                role="assistant",
                content=message_content,
                type="mixed",
                structured_content=youtube_videos,  # Only YouTube data goes here
                mixed_content_data=mixed_content_structure,  # Mixed content structure goes here
                quiz_html=quiz_html if has_quiz else "",
                diagram_image_id=diagram_image_id if has_diagram else None,
                has_diagram=has_diagram,
                has_youtube=has_youtube,
                has_quiz=has_quiz,
                has_code=has_code,
            )

            logger.info(
                f"Created mixed content message with components: diagram={has_diagram}, youtube={has_youtube}, quiz={has_quiz}, code={has_code}"
            )

        except Exception as e:
            logger.error(f"Error creating mixed content message: {e}", exc_info=True)
            # Fallback: create individual messages
            await self._create_fallback_individual_messages(
                chat, tool_results, ai_response
            )

    async def _create_fallback_individual_messages(
        self, chat, tool_results, ai_response
    ):
        """Fallback method to create individual messages if mixed content creation fails"""
        try:
            for tool_result in tool_results:
                await sync_to_async(close_old_connections)()

                if tool_result.message_type == "diagram":
                    diagram_image_id = tool_result.structured_data.get(
                        "diagram_image_id"
                    )
                    await sync_to_async(Message.objects.create)(
                        chat=chat,
                        role="assistant",
                        content=tool_result.content,
                        type="diagram",
                        diagram_image_id=diagram_image_id,
                    )
                elif tool_result.message_type == "youtube":
                    await sync_to_async(Message.objects.create)(
                        chat=chat,
                        role="assistant",
                        content=tool_result.content,
                        type="youtube",
                        structured_content=tool_result.structured_data,
                    )
                elif tool_result.message_type == "quiz":
                    quiz_html = tool_result.structured_data.get("quiz_html", "")
                    await sync_to_async(Message.objects.create)(
                        chat=chat,
                        role="assistant",
                        content=tool_result.content,
                        type="quiz",
                        quiz_html=quiz_html,
                    )
                else:
                    await sync_to_async(Message.objects.create)(
                        chat=chat,
                        role="assistant",
                        content=tool_result.content,
                        type="text",
                    )

            # Create AI response message if present
            if ai_response:
                await sync_to_async(Message.objects.create)(
                    chat=chat, role="assistant", content=ai_response
                )

        except Exception as e:
            logger.error(f"Error in fallback message creation: {e}", exc_info=True)


@login_required
def create_chat(request):
    if request.method == "POST":
        new_prompt = PreferenceService.get_system_prompt(request.user)
        request.session["system_prompt"] = new_prompt
        print(new_prompt)

        message = request.POST.get("prompt", "").strip()

        if not message:
            return JsonResponse(
                {"success": False, "error": "No message provided"}, status=400
            )

        try:
            # Create new chat with trimmed message as title
            chat = Chat.objects.create(
                user=request.user,
                title=message[:30] + "..." if len(message) > 30 else message,
            )

            # Create initial message
            Message.objects.create(chat=chat, content=message.strip(), role="user")

            return JsonResponse(
                {
                    "success": True,
                    "chat_id": chat.id,
                    "redirect_url": f"/chat/{chat.id}/",
                    "title": chat.title,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse(
        {"success": False, "error": "Invalid request method"}, status=405
    )


@login_required
def delete_chat(request, chat_id):
    if request.method == "POST":
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            chat.delete()
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def update_chat_title(request, chat_id):
    if request.method == "POST":
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        data = json.loads(request.body)
        new_title = data.get("title", "").strip()
        if new_title:
            chat.title = new_title
            chat.save()
            return JsonResponse({"success": True})
        return JsonResponse({"error": "Title is required"}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def clear_chat(request, chat_id):
    """Clear all messages from a chat."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)

        # Delete all messages in this chat
        Message.objects.filter(chat=chat).delete()

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def chat_quiz(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)

    # We can still check for a minimum number of messages here before calling the service
    if chat.messages.count() < 3:  # Example check
        return JsonResponse(
            {
                "error": "Not enough conversation content in this chat to generate a meaningful quiz. Please continue the conversation further."
            },
            status=400,
        )

    try:
        # Get chat history in the format the service expects
        history_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in chat.messages.all().order_by("created_at")
        ]

        # Call the refactored service function
        quiz_data = async_to_sync(chat_service.generate_quiz)(
            chat_history_messages=history_messages, chat_id=chat.id
        )

        if quiz_data.get("error"):
            return JsonResponse({"error": quiz_data["error"]}, status=400)

        # Separate content and quiz HTML properly
        processed_quiz_html = quiz_data.get("quiz_html", "")
        content_text = quiz_data.get("content", "Here is your quiz:")

        # Ensure we have clean content
        if not content_text or len(content_text.strip()) < 5:
            content_text = "Here is your quiz:"

    except Exception as e:
        logger.error(f"Quiz generation call failed: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Quiz generation failed: {str(e)}"}, status=500)

    # Save as a quiz message with properly separated content
    quiz_msg = Message.objects.create(
        chat=chat,
        role="assistant",
        type="quiz",
        quiz_html=processed_quiz_html,  # Only HTML goes here
        content=content_text,  # Only text content goes here
    )

    # Also save to question bank (similar to QuizTool)
    try:
        from .tools.quiz_tool import QuizTool

        quiz_tool = QuizTool(chat_service)
        async_to_sync(quiz_tool._save_quiz_to_question_bank)(
            quiz_data={"quiz_html": processed_quiz_html},
            chat=chat,
            user_message="Manual quiz generation",
        )
        logger.info("Manual quiz questions saved to question bank")
    except Exception as e:
        logger.error(f"Error saving manual quiz to question bank: {e}", exc_info=True)

    # Return the HTML string to the client
    return JsonResponse({"quiz_html": processed_quiz_html, "message_id": quiz_msg.id})


@login_required
def study_hub_view(request, chat_id):
    """
    Displays a study hub with flashcards and a question bank for a specific chat.
    """
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)

    # Get all flashcards for this chat
    flashcards = chat.flashcards.all().order_by("created_at")

    # Get all questions from the question bank for this chat
    questions = chat.question_bank.all().order_by("created_at")

    context = {"chat": chat, "flashcards": flashcards, "questions": questions}
    return render(request, "chat/study_hub.html", context)


@login_required
def get_quiz_html(request, message_id):
    """
    An endpoint to fetch the HTML for a specific quiz message.
    """
    message = get_object_or_404(
        Message, id=message_id, chat__user=request.user, type="quiz"
    )
    return JsonResponse(
        {
            "quiz_html": message.quiz_html,
            "message_id": message.id,
            "content": message.content,
        }
    )


@login_required
@require_POST
def edit_message(request, chat_id, message_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        message_to_edit = get_object_or_404(Message, id=message_id, chat=chat)

        if message_to_edit.role != "user":
            return JsonResponse(
                {"error": "Only user messages can be edited."}, status=403
            )

        if message_to_edit.chat.user != request.user:
            return JsonResponse(
                {"error": "User not authorized to edit this message."}, status=403
            )

        data = json.loads(request.body)
        new_content = data.get("new_content", "").strip()

        if not new_content:
            return JsonResponse({"error": "New content cannot be empty."}, status=400)

        # Update the message
        message_to_edit.content = new_content
        message_to_edit.is_edited = True
        message_to_edit.edited_at = timezone.now()
        message_to_edit.save()

        # Delete all messages that came after the edited message in this chat
        Message.objects.filter(
            chat=chat, created_at__gt=message_to_edit.created_at
        ).delete()

        logger.info(
            f"Message {message_id} in chat {chat_id} edited. Subsequent messages deleted."
        )

        return JsonResponse(
            {
                "success": True,
                "edited_message_id": message_to_edit.id,
                "new_content": message_to_edit.content,
                "is_edited": message_to_edit.is_edited,
                "edited_at": (
                    message_to_edit.edited_at.isoformat()
                    if message_to_edit.edited_at
                    else None
                ),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(
            f"Error editing message {message_id} in chat {chat_id}: {e}", exc_info=True
        )
        return JsonResponse({"error": f"Could not edit message: {str(e)}"}, status=500)


def list_rag_files(request, chat_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        rag_files = chat.rag_files.all().order_by("-uploaded_at")
        files_data = [
            {"id": str(rag_file.id), "name": rag_file.original_filename}
            for rag_file in rag_files
        ]
        return JsonResponse(files_data, safe=False)
    except Chat.DoesNotExist:
        return JsonResponse({"error": "Chat not found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching RAG files for chat {chat_id}: {e}", exc_info=True)
        return JsonResponse({"error": "Could not retrieve RAG files."}, status=500)


# @method_decorator(login_required, name="dispatch")
class ChatRAGFilesView(View):
    async def post(self, request, chat_id):
        MAX_RAG_FILES = 10
        try:
            chat = await sync_to_async(get_object_or_404)(
                Chat, id=chat_id, user=request.user
            )

            if await sync_to_async(chat.rag_files.count)() >= MAX_RAG_FILES:
                return JsonResponse(
                    {"error": f"RAG file limit ({MAX_RAG_FILES}) reached."}, status=400
                )

            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                return JsonResponse({"error": "No file provided."}, status=400)

            # Basic validation for file type (can be expanded)
            allowed_extensions = [".pdf", ".txt"]
            file_name, file_extension = os.path.splitext(uploaded_file.name)
            if file_extension.lower() not in allowed_extensions:
                return JsonResponse(
                    {"error": "Invalid file type. Only PDF and TXT are allowed."},
                    status=400,
                )

            # Create and save the ChatRAGFile instance
            rag_file = ChatRAGFile(
                chat=chat,
                user=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
            )
            files_rag_instance = RAG_pipeline()

            await sync_to_async(
                rag_file.save
            )()  # This will call the upload_to logic in the model

            print("Rag file saved")
            try:
                print(f"files path {rag_file.file.path}")
                print(f"files extension {file_extension}")

                await sync_to_async(files_rag_instance.build_index)(
                    file_paths_and_types=[
                        (
                            rag_file.file.path,
                            file_extension[1:],
                        )
                    ],  # Pass the original filename
                    chat_id=chat_id,
                    rag_files_map={rag_file.file.path: rag_file},  # Pass the mapping
                    incremental=True,  # Add new file without clearing existing ones
                )

                logger.info(f"Successfully built RAG index from file{rag_file.file}")
            except Exception as e:
                logger.error(
                    f"Failed to build RAG index from persisted files: {e}",
                    exc_info=True,
                )

            # Index has been built for the new file - no need to clear it

            return JsonResponse(
                {
                    "success": True,
                    "file": {
                        "id": str(rag_file.id),
                        "name": rag_file.original_filename,
                    },
                },
                status=201,
            )

        except (
            Chat.DoesNotExist
        ):  # Should be caught by get_object_or_404 if that's what it raises as Http404
            return JsonResponse({"error": "Chat not found"}, status=404)
        except Exception as e:
            logger.error(
                f"Error uploading RAG file for chat {chat_id}: {e}", exc_info=True
            )
            return JsonResponse({"error": "Could not upload RAG file."}, status=500)

    async def delete(self, request, chat_id, file_id):
        try:
            try:
                chat = await sync_to_async(Chat.objects.get)(
                    id=chat_id, user=request.user
                )
            except Chat.DoesNotExist:
                logger.warning(
                    f"Chat not found during RAG file deletion: chat_id={chat_id}, user={request.user.id}"
                )
                return JsonResponse({"error": "Chat not found"}, status=404)

            try:
                rag_file = await sync_to_async(ChatRAGFile.objects.get)(
                    id=file_id, chat=chat, user=request.user
                )
            except ChatRAGFile.DoesNotExist:
                logger.warning(
                    f"RAG file not found during deletion: file_id={file_id}, chat_id={chat_id}"
                )
                return JsonResponse(
                    {"error": "RAG file not found in this chat"}, status=404
                )

            # Delete the actual file from storage
            if rag_file.file:
                # Ensure the file exists before trying to delete
                if await sync_to_async(default_storage.exists)(rag_file.file.name):
                    await sync_to_async(default_storage.delete)(rag_file.file.name)
                    logger.info(
                        f"Successfully deleted file from storage: {rag_file.file.name}"
                    )
                else:
                    logger.warning(
                        f"File not found in storage for {rag_file.file.name}, attempting to delete DB record anyway."
                    )

            # Delete the ChatRAGFile model instance
            rag_file_name_for_log = rag_file.original_filename
            await sync_to_async(rag_file.delete)()
            logger.info(
                f"Successfully deleted ChatRAGFile record for '{rag_file_name_for_log}' (ID: {file_id}) from chat {chat_id}"
            )

            # After file deletion, clear and rebuild vector index
            try:
                await sync_to_async(
                    DocumentChunk.objects.filter(chat_id=chat_id).delete
                )()
                await sync_to_async(
                    ChatVectorIndex.objects.filter(chat_id=chat_id).delete
                )()
                logger.info(
                    f"Cleared vector index for chat {chat_id} after file deletion"
                )
            except Exception as e:
                logger.error(f"Error clearing vector index after deletion: {e}")

            return JsonResponse(
                {
                    "success": True,
                    "message": "File removed from RAG context successfully.",
                },
                status=200,
            )

        except Exception as e:  # Catch any other unexpected errors
            logger.error(
                f"Unexpected error deleting RAG file {file_id} for chat {chat_id}: {e}",
                exc_info=True,
            )
            return JsonResponse(
                {
                    "error": "Could not delete RAG file due to an unexpected server error."
                },
                status=500,
            )


# Use Django's CSRF protection in production with {% csrf_token %} in forms
@csrf_exempt
def generate_flashcards_view(request):
    if request.method == "POST":
        if not flashcard_model:
            return JsonResponse(
                {"error": "Flashcard generation model not configured."}, status=500
            )

        try:
            print(f"Request's BODY:\n {request.body}")
            data = json.loads(request.body)
            print(f"Data in json format: \n {data}")
            topic = data.get("topic", "").strip()  # If using dictionary access
            print(f"The TOPIC IS: {topic}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)
        # except Exception as e: # If using Pydantic and validation fails
        # return JsonResponse({"error": f"Invalid input: {e}"}, status=400)

        if not topic:
            return JsonResponse({"error": "Topic is required."}, status=400)

        prompt = f"""Generate a list of flashcards for the topic of "{topic}". 
                    Each flashcard should have a term and a concise definition. Format the output as a list of "Term: Definition" pairs, one per line, the text for a single cards must all be included in a single line
                    no linebreakes are allowed for a single entry. Example:
Hello: Hola
Goodbye: Adiós"""

        try:
            response = flashcard_model.generate_content(prompt)
            print(f"Response text {response.text}")
            text = response.text.strip()
            print(f"flashcard model text {text}")

            flashcards = []
            for index, line in enumerate(text.splitlines()):
                append_to_which = None
                line_to_append = ""
                if not ":" in line and index == 0:
                    append_to_which = 0
                    line_to_append = line
                elif not ":" in line and index == 1:
                    append_to_which = 1
                    line_to_append = line
                elif not ":" in line and index != 0 and index != 1:
                    line_to_append = line
                if ":" in line:
                    parts = line.split(":", 1)

                    if line_to_append and append_to_which == 0:
                        parts[append_to_which] = (
                            line_to_append + f" {parts[append_to_which]}"
                        )
                    elif line_to_append and append_to_which == 1:
                        parts[append_to_which] += f" {line_to_append}"

                    print(f"Parts are {parts}")
                    term = parts[0].strip()
                    print(f"Term is {term}")
                    definition = parts[1].strip() if len(parts) > 1 else ""
                    print(f"Definition is {definition}")
                    if (
                        term and definition
                    ):  # Ensure both term and definition are present
                        flashcards.append({"term": term, "definition": definition})
                print(f"Flashcards here: \n {flashcards}")
            if not flashcards:
                return JsonResponse(
                    {
                        "error": "No valid flashcards were generated by the model. The response might have been empty or not in the expected format.",
                        "details": text,
                    },
                    status=500,
                )

            return JsonResponse({"flashcards": flashcards})

        except Exception as e:
            # Log the full exception for debugging
            print(f"Error during flashcard generation: {e}")
            # Provide a generic error to the user
            return JsonResponse(
                {"error": f"An error occurred while generating flashcards: {str(e)}"},
                status=500,
            )

    # For GET request, render the page with the form
    return render(request, "chat/flashcards.html")


@login_required
def serve_diagram_image(request, diagram_id):
    logger.info(f"[serve_diagram_image] Received request for diagram_id: {diagram_id}")
    try:
        diagram_image_instance = get_object_or_404(
            DiagramImage, id=diagram_id, user=request.user
        )
        logger.info(
            f"[serve_diagram_image] Found DiagramImage record with ID: {diagram_image_instance.id}, Filename: {diagram_image_instance.filename}"
        )
        logger.info(
            f"[serve_diagram_image] Content type: {diagram_image_instance.content_type}"
        )
        image_data_length = (
            len(diagram_image_instance.image_data)
            if diagram_image_instance.image_data
            else 0
        )
        logger.info(
            f"[serve_diagram_image] Length of image_data from DB: {image_data_length} bytes"
        )

        if image_data_length == 0:
            logger.error(
                f"[serve_diagram_image] Image data for ID {diagram_id} is empty in the database!"
            )
            # Return 404 if data is empty
            return HttpResponse("Image data not found or is empty.", status=404)

        logger.info(
            f"[serve_diagram_image] Returning HttpResponse for diagram ID: {diagram_id}"
        )
        return HttpResponse(
            diagram_image_instance.image_data,
            content_type=diagram_image_instance.content_type,
        )
    except Http404:
        logger.warning(
            f"DiagramImage with id {diagram_id} not found or user {request.user.id} not authorized."
        )
        return HttpResponse("Diagram not found or access denied.", status=404)
    except Exception as e:
        logger.error(f"Error serving diagram image {diagram_id}: {e}", exc_info=True)
        return HttpResponse("Error serving diagram.", status=500)
