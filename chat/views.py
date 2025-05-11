# chat/views.py
import logging
from django.http import JsonResponse
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Chat, Message, ChatRAGFile
from groq import Groq, APIStatusError
from django.utils.safestring import mark_safe
import html
from django.views import View
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.core.files.storage import default_storage
import io
import os
import json
from .services import ChatService, LangChainRAG
from .preference_service import PreferenceService
from django.views.decorators.http import require_POST
import re
from django.utils import timezone
chat_service = ChatService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Groq client.
groq_client = Groq()


@method_decorator(login_required, name='dispatch')
class ChatListView(ListView):
    model = Chat
    template_name = 'chat/chat_list.html'
    context_object_name = 'chats'

    # get_queryset is used by ListView, so keep it
    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user).order_by('-updated_at')


@method_decorator(login_required, name='dispatch')
class ChatView(View):
    template_name = 'chat/chat.html'

    def get(self, request, chat_id=None):
        # Handle AJAX requests for message updates
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
                messages = list(chat.messages.all().order_by(
                    'created_at').values('role', 'content'))
                return JsonResponse({'messages': messages})
            except Chat.DoesNotExist:
                return JsonResponse({'error': 'Chat not found'}, status=404)

        chats = Chat.objects.filter(user=request.user).order_by('-updated_at')
        is_new_chat = request.path == '/chat/new/'

        # Handle new chat
        if is_new_chat:
            temp_id = f'temp_{int(time.time())}'
            return render(request, self.template_name, {
                "current_chat": {
                    'id': temp_id,
                    'title': 'New Chat'
                },
                "conversation": [],
                "chats": chats,
                "is_new_chat": True
            })

        # Handle existing chat
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
                messages = chat.messages.all().order_by('created_at')
                conversation = []
                for i, msg in enumerate(messages):
                    if msg.content == '' and i > 0 and msg.role == 'assistant':
                        conversation.append({
                            'role': msg.role, 
                            'html': msg.quiz_html, 
                            'id': msg.id, 
                            'created_at': msg.created_at.isoformat()
                        })
                    else:
                        conversation.append({
                            'role': msg.role, 
                            'text': msg.content, 
                            'id': msg.id, 
                            'is_edited': msg.is_edited,
                            'edited_at': msg.edited_at.isoformat() if msg.edited_at else None,
                            'created_at': msg.created_at.isoformat()
                        })
                return render(request, self.template_name, {
                    "current_chat": chat,
                    "conversation": conversation,
                    "chats": chats,
                    "is_new_chat": False
                })
            except Chat.DoesNotExist:
                return redirect('new_chat')

        # Default to chat list or new chat
        return redirect('new_chat')


@method_decorator(login_required, name='dispatch')
class ChatStreamView(View):
    def post(self, request, chat_id):
        try:
            logger.info(f"ChatStreamView.post called for chat_id={chat_id}")
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            logger.info(f"Got chat: {chat}")

            user_typed_prompt = request.POST.get('prompt', '').strip()
            logger.info(f"User typed prompt: {user_typed_prompt}")

            uploaded_file = request.FILES.get('file')
            logger.info(f"Uploaded file: {uploaded_file}")

            file_info_for_llm = None # To store dict from extract_text_from_uploaded_file
            prompt_for_display_and_db = user_typed_prompt # This is what's saved and shown as user message
            llm_query_content = user_typed_prompt # This will be augmented with file text for LLM

            if uploaded_file:
                file_info_for_llm = chat_service.extract_text_from_uploaded_file(uploaded_file)
                # prompt_for_display_and_db is already user_typed_prompt which contains the file attachment string from JS
                # llm_query_content will be further augmented
                llm_query_content = (
                    f"{user_typed_prompt}\n\n"
                    f"[Content from uploaded file '{file_info_for_llm['filename']}':]\n"
                    f"{file_info_for_llm['text_content']}\n"
                    if user_typed_prompt 
                    else f"[Content from uploaded file '{file_info_for_llm['filename']}':]\n{file_info_for_llm['text_content']}\n"
                )
                logger.info(f"LLM query content augmented with file text from: {file_info_for_llm['filename']}")
                if file_info_for_llm['was_truncated']:
                    logger.info(f"File {file_info_for_llm['filename']} was truncated. Original: {file_info_for_llm['original_char_count']} chars, Final: {file_info_for_llm['final_char_count']} chars.")

            # RAG strength and use_history are no longer relevant for this part of the flow.
            # files_rag for persistent RAG (Part 2) is not built or loaded here.
            # chat_history_rag is completely removed.

            # --- BEGIN: Integrate persisted RAG files ---
            files_rag_instance = None
            rag_mode_active_str = request.POST.get('rag_mode_active', 'true') # Get RAG mode from POST
            rag_mode_active = rag_mode_active_str.lower() == 'true' # Convert to boolean

            if rag_mode_active:
                logger.info("RAG mode is ACTIVE. Attempting to build RAG index from persisted files.")
                active_rag_files = chat.rag_files.all().order_by('-uploaded_at')
                attached_file_names_for_rag_context = []

                if active_rag_files:
                    file_paths_and_types_for_rag = []
                    for rag_file_entry in active_rag_files:
                        file_path = rag_file_entry.file.path # Get the absolute path to the stored file
                        _, file_ext = os.path.splitext(rag_file_entry.original_filename)
                        file_type = file_ext.lower().strip('.') # e.g., 'pdf', 'txt'
                        if file_type in ['pdf', 'txt']: # Only include supported types
                            file_paths_and_types_for_rag.append((file_path, file_type))
                            attached_file_names_for_rag_context.append(rag_file_entry.original_filename)
                        else:
                            logger.warning(f"Skipping RAG file {rag_file_entry.original_filename} due to unsupported type: {file_type}")
                    
                    if file_paths_and_types_for_rag:
                        logger.info(f"Building RAG index from persisted files: {attached_file_names_for_rag_context}")
                        files_rag_instance = LangChainRAG() # model is default
                        try:
                            files_rag_instance.build_index(file_paths_and_types_for_rag)
                            logger.info(f"Successfully built RAG index from {len(file_paths_and_types_for_rag)} persisted files.")
                        except Exception as e:
                            logger.error(f"Failed to build RAG index from persisted files: {e}", exc_info=True)
                            # files_rag_instance will remain None or be an empty RAG instance
                            # Optionally notify user via SSE?
            else:
                logger.info("RAG mode is INACTIVE. Skipping RAG index build.")
                attached_file_names_for_rag_context = [] # Ensure it's defined for stream_response
            # --- END: Integrate persisted RAG files ---

            is_reprompt_after_edit = request.POST.get("is_reprompt_after_edit") == "true"

            # Determine if this is the very first message turn in a new chat.
            # chat.messages.count() would be 1 if create_chat just saved the first message.
            is_handling_continuation_of_new_chat = (chat.messages.count() == 1 and 
                                                  chat.messages.first().content == user_typed_prompt)

            if not is_handling_continuation_of_new_chat and not is_reprompt_after_edit:
                logger.info("User message will be saved in stream_response upon successful LLM interaction.")
            elif is_reprompt_after_edit:
                logger.info("Skipping user message save as this is a re-prompt after an edit (no new user message to save).")
            else: # is_handling_continuation_of_new_chat is true
                logger.info("Skipping user message save in ChatStreamView as create_chat already handled the initial user message.")

            if chat.title == "New Chat" and user_typed_prompt and not is_reprompt_after_edit:
                # Update title only for genuinely new interactions, not for re-prompts after edit
                chat_service.update_chat_title(chat, user_typed_prompt)
                logger.info("Chat title updated.")

            system_prompt_text = PreferenceService.get_system_prompt(request.user)
            messages_for_llm = [{"role": "system", "content": system_prompt_text}]
            
            chat_history_db = chat_service.get_chat_history(chat) # All messages currently in DB

            if is_handling_continuation_of_new_chat:
                logger.info("First turn of new chat: LLM history will start with system prompt, current query will be added next.")
            else:
                for msg_data in chat_history_db:
                    messages_for_llm.append({"role": msg_data.role, "content": msg_data.content})
                logger.info(f"Ongoing chat or re-prompt: Added {len(chat_history_db)} messages from DB to LLM context.")
            
            messages_for_llm.append({"role": "user", "content": llm_query_content})
            
            logger.info(f"Message history prepared with {len(messages_for_llm)} messages for LLM. Last user message for LLM: {llm_query_content[:200]}...")

            is_new_chat_bool = chat.messages.count() == 1 # This flag is used by stream_completion.
                                                          # It's true if this is the first turn (one user msg, one assistant to come)

            return self.stream_response(
                chat=chat,
                messages_for_llm=messages_for_llm,
                query_for_rag=user_typed_prompt, 
                files_rag_instance=files_rag_instance, # Pass the instance built from ChatRAGFiles
                is_new_chat=is_new_chat_bool,
                current_user_prompt_for_saving = user_typed_prompt if not (is_handling_continuation_of_new_chat or is_reprompt_after_edit) else None, # Pass prompt to save, or None
                attached_file_name_for_rag=", ".join(attached_file_names_for_rag_context) if attached_file_names_for_rag_context else None, 
                file_info_for_truncation_warning=file_info_for_llm # Pass dict for SSE warning
            )

        except Exception as e:
            logger.error(f"Exception in ChatStreamView.post: {str(e)}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)

    def stream_response(self, chat, messages_for_llm, query_for_rag=None, files_rag_instance=None, is_new_chat=False, current_user_prompt_for_saving=None, attached_file_name_for_rag=None, file_info_for_truncation_warning=None):
        def event_stream():
            user_message_saved = False # Flag to track if user message has been saved
            try:
                logger.info("stream_response.event_stream started.")
                accumulated_response = ""

                # Send truncation warning if applicable
                if file_info_for_truncation_warning and file_info_for_truncation_warning['was_truncated']:
                    warning_msg = (
                        f"The content of '{file_info_for_truncation_warning['filename']}' was truncated "
                        f"(from {file_info_for_truncation_warning['original_char_count']} to {file_info_for_truncation_warning['final_char_count']} characters) "
                        f"because it was too long for direct processing with your message. "
                        f"For full document analysis, please use the 'Manage RAG Context' feature (coming soon)."
                    )
                    logger.info(f"Sending truncation warning to client: {warning_msg}")
                    yield f"data: {json.dumps({'type': 'file_info', 'status': 'truncated', 'message': warning_msg})}\n\n"

                message_count = len(messages_for_llm) # This is messages BEFORE enforce_token_limit
                max_tokens_for_llm = 7000 # INCREASED for more history (was 3500/4500 based on message_count)
                logger.info(f"[ChatStreamView.stream_response] Attempting to use max_tokens_for_llm: {max_tokens_for_llm} for ChatService's enforce_token_limit. Original message count for LLM (before limit): {message_count}")

                stream = chat_service.stream_completion(
                    messages=messages_for_llm, # This now contains the augmented prompt
                    query=query_for_rag,    # For explicit RAG (Part 2), not used if files_rag_instance is None
                    files_rag=files_rag_instance, # Explicitly passed, None for Part 1
                    max_tokens=max_tokens_for_llm,
                    chat_id=chat.id, # Still useful for other things within stream_completion
                    is_new_chat=is_new_chat,
                    attached_file_name=attached_file_name_for_rag # For RAG context (Part 2)
                )
                
                if type(stream) == str: # If stream_completion returned a string (direct RAG output)
                    # This is now considered a direct response, not an error.
                    if not user_message_saved and current_user_prompt_for_saving:
                        chat_service.create_message(chat, 'user', current_user_prompt_for_saving)
                        user_message_saved = True # Ensure flag is set if we proceed
                        logger.info(f"User message '{current_user_prompt_for_saving[:50]}...' saved to DB (direct RAG output case).")

                    # Save this direct string output as the assistant's message
                    chat_service.create_message(chat, 'assistant', stream) # 'stream' here is the RAG content string
                    logger.info(f"Direct RAG output saved as assistant message: {stream[:100]}...")
                    
                    # Send it as regular content to the client
                    yield f"data: {json.dumps({'type': 'content', 'content': stream})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n" # Indicate completion
                    
                    # Optionally, if you still want RAG metadata in this case:
                    if files_rag_instance:
                         rag_stats = {
                            'file_chunks_used': len(files_rag_instance.chunks) if files_rag_instance and hasattr(files_rag_instance, 'chunks') else 0,
                         }
                         yield f"data: {json.dumps({'type': 'metadata', 'content': rag_stats})}\n\n"
                    return # End the generator as we've sent the complete direct response
                else:
                    # This is the normal LLM stream iterator
                    logger.info("Got stream from chat_service.stream_completion.")
                    first_chunk_processed = False
                    for chunk in stream:
                        content = getattr(chunk.choices[0].delta, "content", None)
                        if content:
                            # Save the user's message on first successful content chunk from LLM, if it's meant to be saved
                            if not user_message_saved and current_user_prompt_for_saving:
                                chat_service.create_message(chat, 'user', current_user_prompt_for_saving)
                                user_message_saved = True
                                logger.info(f"User message '{current_user_prompt_for_saving[:50]}...' saved to DB after successful LLM stream start.")
                            
                            accumulated_response += content
                            yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                            if not first_chunk_processed:
                                first_chunk_processed = True

                if accumulated_response: # Implies successful stream
                    # If user message wasn't saved due to empty stream but no error, save it now if needed.
                    if not user_message_saved and current_user_prompt_for_saving:
                        chat_service.create_message(chat, 'user', current_user_prompt_for_saving)
                        user_message_saved = True # Though already past stream, ensure flag is correct
                        logger.info(f"User message '{current_user_prompt_for_saving[:50]}...' saved to DB before saving assistant response (empty stream case).")

                    chat_service.create_message(chat, 'assistant', accumulated_response)
                    logger.info("Assistant message created from accumulated stream.")
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
                    # Metadata about RAG (Part 2) usage - only if files_rag_instance was used
                    if files_rag_instance:
                        rag_stats = {
                            'file_chunks_used': len(files_rag_instance.chunks) if files_rag_instance and hasattr(files_rag_instance, 'chunks') else 0,
                            # 'history_chunks_used': 0 # chat_history_rag removed
                        }
                        yield f"data: {json.dumps({'type': 'metadata', 'content': rag_stats})}\n\n"

            except APIStatusError as e:
                logger.error(f"Groq APIStatusError in stream_response.event_stream: Status {e.status_code}, Response: {e.response.text if e.response else 'No response body'}", exc_info=True)
                user_message = "An API error occurred with the language model."
                if e.status_code == 413:
                    try:
                        error_detail = e.response.json()
                        if error_detail.get('error', {}).get('type') == 'tokens' or 'tokens per minute (TPM)' in error_detail.get('error', {}).get('message', ''):
                            user_message = "The request is too large for the model. Please try reducing your message size or shortening the conversation if the history is very long."
                    except json.JSONDecodeError:
                        # Fallback if response is not JSON, though Groq usually sends JSON errors
                        if "Request too large" in str(e) or "tokens per minute (TPM)" in str(e): # Check string representation as a fallback
                             user_message = "The request is too large for the model. Please try reducing your message size or shortening the conversation if the history is very long."
                
                yield f"data: {json.dumps({'type': 'error', 'content': user_message})}\n\n"

            except Exception as e:
                logger.error(f"Generic exception in stream_response.event_stream: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        logger.info("StreamingHttpResponse returned.")
        return response


@login_required
def create_chat(request):
    if request.method == "POST":

        new_prompt = PreferenceService.get_system_prompt(request.user)
        request.session['system_prompt'] = new_prompt
        print(new_prompt)

        message = request.POST.get("prompt", "").strip()

        if not message:
            return JsonResponse({
                'success': False,
                'error': 'No message provided'
            }, status=400)

        try:
            # Create new chat with trimmed message as title
            chat = Chat.objects.create(
                user=request.user,
                title=message[:30] + "..." if len(message) > 30 else message
            )

            # Create initial message
            Message.objects.create(
                chat=chat,
                content=message.strip(),
                role='user'
            )

            return JsonResponse({
                'success': True,
                'chat_id': chat.id,
                'redirect_url': f'/chat/{chat.id}/'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)



@login_required
def delete_chat(request, chat_id):
    if request.method == "POST":
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            chat.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def update_chat_title(request, chat_id):
    if request.method == 'POST':
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        data = json.loads(request.body)
        new_title = data.get('title', '').strip()
        if new_title:
            chat.title = new_title
            chat.save()
            return JsonResponse({'success': True})
        return JsonResponse({'error': 'Title is required'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def clear_chat(request, chat_id):
    """Clear all messages from a chat."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)

        # Delete all messages in this chat
        Message.objects.filter(chat=chat).delete()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def chat_quiz(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    messages = chat.messages.filter(
        role__in=['user', 'assistant']).order_by('created_at')
    content_text = "\n".join(m.content for m in messages if m.content)
    
    user_messages_count = messages.filter(role='user').count()
    assistant_messages_count = messages.filter(role='assistant').count()

    # Previous threshold, adjust if needed, e.g. messages.count() < 5 or len(content_text) < 500
    if user_messages_count < 2 or assistant_messages_count < 1 or len(content_text) < 200: 
        return JsonResponse({'error': 'Not enough diverse conversation content in this chat to generate a meaningful quiz. Please continue the conversation further.'}, status=400)

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
**Output ONLY the HTML for the quiz. DON'T MENTION "QUIZ NUMBER" in the HTML. Do NOT include any explanations, answers, or text outside the HTML.**
Conversation:

{content_text}
** DON'T TELL THE USER ANYTHING AFTER THE QUIZ IS GENERATED.**
** DON'T SAY WHAT THE CORRECT ANSWER IS**

"""

    try:
        quiz_html_response = chat_service.get_completion(
            messages=[{"role": "user", "content": prompt}],
            query=prompt, 
            max_tokens=1500, # Was 1024, can be 1500 for potentially larger HTML
            chat_id=chat.id,
            is_new_chat=False
        )
        
        # Extract only the HTML part, assuming LLM might still add extra text
        # This regex looks for the starting div of a quiz question.
        match = re.search(r'(<div class="quiz-question".*)', quiz_html_response, re.DOTALL)
        if match:
            processed_quiz_html = match.group(1)
        else:
            # If no specific quiz structure found, take the whole response, but log a warning.
            logger.warning(f"Could not find specific quiz HTML structure in LLM response. Using raw response: {quiz_html_response}")
            processed_quiz_html = quiz_html_response 

    except Exception as e:
        logger.error(f"Quiz generation call failed: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Quiz generation failed: {str(e)}'}, status=500)

    # Save as a quiz message, storing the HTML string in quiz_html
    quiz_msg = Message.objects.create(
        chat=chat,
        role='assistant',
        type='quiz',
        quiz_html=processed_quiz_html, # Storing HTML string here
        content='' 
    )

    # Return the HTML string to the client
    return JsonResponse({'quiz_html': processed_quiz_html, 'message_id': quiz_msg.id})


@login_required
@require_POST
def edit_message(request, chat_id, message_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        message_to_edit = get_object_or_404(Message, id=message_id, chat=chat)

        if message_to_edit.role != 'user':
            return JsonResponse({'error': 'Only user messages can be edited.'}, status=403)
        
        if message_to_edit.chat.user != request.user:
            return JsonResponse({'error': 'User not authorized to edit this message.'}, status=403)

        data = json.loads(request.body)
        new_content = data.get('new_content', '').strip()

        if not new_content:
            return JsonResponse({'error': 'New content cannot be empty.'}, status=400)

        # Update the message
        message_to_edit.content = new_content
        message_to_edit.is_edited = True
        message_to_edit.edited_at = timezone.now()
        message_to_edit.save()

        # Delete all messages that came after the edited message in this chat
        Message.objects.filter(chat=chat, created_at__gt=message_to_edit.created_at).delete()
        
        logger.info(f"Message {message_id} in chat {chat_id} edited. Subsequent messages deleted.")

        return JsonResponse({
            'success': True,
            'edited_message_id': message_to_edit.id,
            'new_content': message_to_edit.content,
            'is_edited': message_to_edit.is_edited,
            'edited_at': message_to_edit.edited_at.isoformat() if message_to_edit.edited_at else None
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error editing message {message_id} in chat {chat_id}: {e}", exc_info=True)
        return JsonResponse({'error': f'Could not edit message: {str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class ChatRAGFilesView(View):
    def get(self, request, chat_id):
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            rag_files = chat.rag_files.all().order_by('-uploaded_at')
            files_data = [
                {"id": str(rag_file.id), "name": rag_file.original_filename}
                for rag_file in rag_files
            ]
            return JsonResponse(files_data, safe=False)
        except Chat.DoesNotExist:
            return JsonResponse({'error': 'Chat not found'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching RAG files for chat {chat_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Could not retrieve RAG files.'}, status=500)

    def post(self, request, chat_id):
        MAX_RAG_FILES = 3
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)

            if chat.rag_files.count() >= MAX_RAG_FILES:
                return JsonResponse({'error': f'RAG file limit ({MAX_RAG_FILES}) reached.'}, status=400)

            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return JsonResponse({'error': 'No file provided.'}, status=400)
            
            # Basic validation for file type (can be expanded)
            allowed_extensions = ['.pdf', '.txt']
            file_name, file_extension = os.path.splitext(uploaded_file.name)
            if file_extension.lower() not in allowed_extensions:
                return JsonResponse({'error': 'Invalid file type. Only PDF and TXT are allowed.'}, status=400)

            # Create and save the ChatRAGFile instance
            rag_file = ChatRAGFile(
                chat=chat,
                user=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name
            )
            rag_file.save() # This will call the upload_to logic in the model

            return JsonResponse({
                'success': True,
                'file': {'id': str(rag_file.id), 'name': rag_file.original_filename}
            }, status=201)

        except Chat.DoesNotExist: # Should be caught by get_object_or_404 if that's what it raises as Http404
            return JsonResponse({'error': 'Chat not found'}, status=404)
        except Exception as e:
            logger.error(f"Error uploading RAG file for chat {chat_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Could not upload RAG file.'}, status=500)

    def delete(self, request, chat_id, file_id):
        try:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
            except Chat.DoesNotExist:
                logger.warning(f"Chat not found during RAG file deletion: chat_id={chat_id}, user={request.user.id}")
                return JsonResponse({'error': 'Chat not found'}, status=404)

            try:
                rag_file = ChatRAGFile.objects.get(id=file_id, chat=chat, user=request.user)
            except ChatRAGFile.DoesNotExist:
                logger.warning(f"RAG file not found during deletion: file_id={file_id}, chat_id={chat_id}")
                return JsonResponse({'error': 'RAG file not found in this chat'}, status=404)

            # Delete the actual file from storage
            if rag_file.file:
                # Ensure the file exists before trying to delete
                if default_storage.exists(rag_file.file.name):
                    default_storage.delete(rag_file.file.name)
                    logger.info(f"Successfully deleted file from storage: {rag_file.file.name}")
                else:
                    logger.warning(f"File not found in storage for {rag_file.file.name}, attempting to delete DB record anyway.")
            
            # Delete the ChatRAGFile model instance
            rag_file_name_for_log = rag_file.original_filename
            rag_file.delete()
            logger.info(f"Successfully deleted ChatRAGFile record for '{rag_file_name_for_log}' (ID: {file_id}) from chat {chat_id}")

            return JsonResponse({'success': True, 'message': 'File removed from RAG context successfully.'}, status=200)

        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error deleting RAG file {file_id} for chat {chat_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Could not delete RAG file due to an unexpected server error.'}, status=500)
