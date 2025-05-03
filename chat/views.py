# chat/views.py
import logging
from django.http import JsonResponse
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Chat, Message
from groq import Groq
from django.utils.safestring import mark_safe
import html
from django.views import View
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.core.files.storage import default_storage
import io
import os
import json
from .services import ChatService
from .preference_service import PreferenceService
from django.views.decorators.http import require_POST
import re
chat_service = ChatService()

logger = logging.getLogger(__name__)

# Detailed system prompt for the "Learning How to Learn" expert.
SYSTEM_PROMPT = (
    "You are LearningMaster, an expert in the principles of 'Learning How to Learn'. "
    "You possess extensive knowledge of effective learning techniques, cognitive psychology, memory retention strategies, "
    "and resource recommendations across a wide range of subjects. Your goal is to help students study any subject by providing "
    "clear, personalized, and effective study strategies that take into account their unique learning preferences. "
    "Before answering any questions, if the student's preferred learning style (e.g., visual, auditory, kinesthetic, reading/writing) "
    "is not clearly stated in their prompt, ask a clarifying question (or questions) to get that information, and then end your message "
    "with the marker <<END_OF_QUESTION>>. Do not provide any further explanation until the student provides their learning style. "
    "In addition to providing personalized study strategies, you excel at creating interactive quizzes that cover "
    "the most vital parts of a lecture. When asked, generate multiple-choice quizzes with 4 answer options per question. "
    "Each quiz should be output as a complete HTML snippet that includes inline CSS and JavaScript so that the quiz is interactive—"
    "allowing the user to select an answer and then see whether they chose correctly. "
    "Once you have the necessary information, provide a full, detailed answer and include recommendations for high-quality, freely available resources."
)

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
                for msg in messages:
                    if msg.content == '':
                        print("here")
                        conversation.append(
                            {'role': msg.role, 'html': msg.quiz_html})
                    else:
                        conversation.append(
                            {'role': msg.role, 'text': msg.content})
                for i in conversation:
                    print(i)
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

            prompt_text = request.POST.get('prompt', '').strip()
            logger.info(f"Prompt text: {prompt_text}")

            uploaded_file = request.FILES.get('file')
            logger.info(f"Uploaded file: {uploaded_file}")

            attached_file_name = uploaded_file.name if uploaded_file else None

            rag_strength = request.POST.get('rag_strength', 'high')
            use_history = request.POST.get('use_history', 'true') == 'true'

            files_rag = None
            chat_history_rag = None
            file_path, file_ext = "", ""
            if uploaded_file:
                logger.info("Processing uploaded file for RAG context.")
                file_path, file_ext = chat_service.process_file(uploaded_file)
                saved_path = chat_service.save_file(chat.id, uploaded_file)
                logger.info(f"File saved at: {saved_path}")
                if file_path:
                    files_rag = chat_service.build_rag(
                        file_path, file_ext, chat_id=chat.id)
                    logger.info("LangChain RAG index built.")

            # Only use chat history for existing chats (not new chats)
            is_new_chat = chat.title == "New Chat"
            if use_history and not is_new_chat and (not uploaded_file or request.POST.get('include_history', 'false') == 'true'):
                logger.info("Using chat history for RAG context.")
                chat_history = chat_service.get_chat_history(chat)
                chat_history_text = "\n".join(
                    [f"{msg.role}: {msg.content}" for msg in chat_history])
                if chat_history_text.strip():
                    chat_history_rag = chat_service.build_rag_from_text(
                        chat_history_text, chat_id=chat.id)
                    logger.info(
                        f"History index built with {len(chat_history_rag.chunks) if chat_history_rag else 0} chunks")

            # Save user message
            chat_service.create_message(chat, 'user', prompt_text)
            logger.info("User message created.")

            # Update chat title if it's a new chat
            if chat.title == "New Chat" and prompt_text:
                chat_service.update_chat_title(chat, prompt_text)
                logger.info("Chat title updated.")

            # Prepare message history
            system_prompt = request.session.get('system_prompt', SYSTEM_PROMPT)
            messages = [{"role": "user", "content": system_prompt}]
            chat_history = chat_service.get_chat_history(chat)
            for msg in chat_history:
                # Map any non-user role to 'assistant'
                role = msg.role if msg.role == 'user' else 'assistant'
                messages.append({"role": role, "content": msg.content})
            # Only send the user's actual message to the LLM, not the '[Attached file: ...]' string
            messages.append({"role": "user", "content": prompt_text})

            # Filter to only user/assistant roles (defensive)
            messages = [m for m in messages if m["role"] in ("user", "assistant")]

            logger.info(
                f"Message history prepared with {len(messages)} messages")

            # Stream the response
            return self.stream_response(
                chat,
                messages,
                query=prompt_text,
                files_rag=files_rag,
                chat_history_rag=chat_history_rag,
                is_new_chat=is_new_chat,
                attached_file_name=attached_file_name
            )

        except Exception as e:
            logger.error(
                f"Exception in ChatStreamView.post: {str(e)}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)

    def stream_response(self, chat, messages, query=None, files_rag=None, chat_history_rag=None, is_new_chat=False, attached_file_name=None):
        def event_stream():
            try:
                logger.info("stream_response.event_stream started.")
                accumulated_response = ""

                message_count = len(messages)
                max_tokens = 3500 if message_count < 10 else 4500

                # Filter to only user/assistant roles (defensive)
                filtered_messages = [m for m in messages if m["role"] in ("user", "assistant")]

                stream = chat_service.stream_completion(
                    filtered_messages,
                    query=query,
                    max_tokens=max_tokens,
                    files_rag=files_rag,
                    chat_history_rag=chat_history_rag,
                    chat_id=chat.id,
                    is_new_chat=is_new_chat,
                    attached_file_name=attached_file_name
                )
                logger.info("Got stream from chat_service.stream_completion.")

                for chunk in stream:
                    # Groq streaming returns objects with .choices[0].delta.content
                    content = getattr(chunk.choices[0].delta, "content", None)
                    if content:
                        accumulated_response += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                if accumulated_response:
                    chat_service.create_message(
                        chat, 'assistant', accumulated_response)
                    logger.info("Assistant message created.")

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                    if files_rag or chat_history_rag:
                        rag_stats = {
                            'file_chunks_used': len(files_rag.chunks) if files_rag else 0,
                            'history_chunks_used': len(chat_history_rag.chunks) if chat_history_rag else 0
                        }
                        yield f"data: {json.dumps({'type': 'metadata', 'content': rag_stats})}\n\n"

            except Exception as e:
                logger.error(
                    f"Exception in stream_response.event_stream: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

                # Fallback to non-RAG response if RAG fails
                try:
                    if query and (files_rag or chat_history_rag):
                        logger.info("Attempting fallback to non-RAG response")
                        fallback_messages = [msg for msg in messages if not (
                            'relevant context' in msg['content'].lower())]
                        # Filter to only user/assistant roles (defensive)
                        fallback_messages = [m for m in fallback_messages if m["role"] in ("user", "assistant")]
                        fallback_response = chat_service.get_completion(
                            fallback_messages,
                            max_tokens=3500,
                            chat_id=chat.id,
                            is_new_chat=is_new_chat
                        )
                        yield f"data: {json.dumps({'type': 'info', 'content': 'RAG retrieval failed. Using standard response instead.'})}\n\n"
                        if fallback_response:
                            yield f"data: {json.dumps({'type': 'content', 'content': fallback_response})}\n\n"
                            chat_service.create_message(
                                chat, 'assistant', fallback_response)
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback attempt also failed: {str(fallback_error)}", exc_info=True)

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
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


# chat/views.py (updated quiz_view)


@login_required
def quiz_view(request):
    if request.method == "POST":
        lecture_text = request.POST.get("lecture_text", "").strip()
        if not lecture_text:
            return HttpResponse("Lecture text is required to generate a quiz.", status=400)

        prefs = request.user.get_learning_preferences()

        # Build a dedicated prompt for quiz generation with user preferences
        quiz_prompt = (
            "You are LearningMaster, an expert in 'Learning How to Learn' and a skilled quizzer. "
            f"The student prefers {prefs['learning_style']} learning styles and {prefs['study_time']} study sessions. "
            "Generate an interactive multiple-choice quiz based on the following lecture text. "
            f"{'Include visual elements and diagrams where possible.' if prefs['learning_style'] == 'visual' else ''} "
            "Each question should have 4 possible answers, with only one correct answer. "
            "Output the quiz as a complete HTML snippet that includes inline CSS and JavaScript. "
            "The HTML should display the quiz questions, provide radio button options for each, "
            "and include a 'Check Answer' button that reveals whether the selected answer is correct or not. "
            "Lecture text:\n\n" + lecture_text
        )

        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": quiz_prompt}],
                temperature=1,
                max_completion_tokens=4096,
                top_p=1,
                stream=False,
                stop=None,
            )
        except Exception as e:
            return HttpResponse(f"Error calling Groq API: {e}", status=500)

        # Unescape HTML entities in the output and mark it as safe.
        raw_quiz = completion.choices[0].message.content
        unescaped_quiz = html.unescape(raw_quiz)
        quiz_html = mark_safe(unescaped_quiz)

        # Extract only the HTML part
        match = re.search(r'(<div class="quiz-question".*)',
                          quiz_html, re.DOTALL)
        if match:
            quiz_html = match.group(1)

        context = {
            "quiz_html": quiz_html,
            "lecture_text": lecture_text,
        }
        return render(request, "chat/quiz.html", context)

    return render(request, "chat/quiz.html")


@login_required
def send_message(request, chat_id):
    """Handle sending a message in a specific chat."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Get the current chat
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)

        # Parse the incoming message
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()

        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        # Save the user message to this chat
        chat_service.create_message(chat, 'user', user_message)

        # Get the AI response using the generate_response method
        assistant_response = chat_service.generate_response(chat, request.user)

        # Save the assistant's response to this chat
        chat_service.create_message(chat, 'assistant', assistant_response)

        return JsonResponse({
            'response': assistant_response,
            'chat_id': chat.id,
            'chat_title': chat.title
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    content_text = "\n".join(m.content for m in messages)
    if messages.count() < 5 or len(content_text) < 500:
        return JsonResponse({'error': 'Not enough content in this chat to generate a quiz. Please continue the conversation first.'}, status=400)

    prompt = f"""
Create a multiple-choice quiz (4 options per question) based on the following conversation's relevant scientific information only, related to the learning.
For each question, use this HTML structure:
<div class="quiz-question" data-correct="B">
  <div class="font-semibold mb-2">What is 2+2?</div>
  <form>
    <label><input type="radio" name="q1" value="A"> 3</label><br>
    <label><input type="radio" name="q1" value="B"> 4</label><br>
    <label><input type="radio" name="q1" value="C"> 5</label><br>
    <label><input type="radio" name="q1" value="D"> 6</label><br>
    <button type="submit" class="mt-2 px-3 py-1 bg-blue-600 text-white rounded">Check Answer</button>
  </form>
  <div class="quiz-feedback mt-2"></div>
</div>
Replace the question, answers, and correct value as appropriate.
**Output ONLY the HTML for the quiz. Do NOT include any explanations, answers, or text outside the HTML.**
Conversation:

{content_text}
"""

    try:
        quiz_html = chat_service.get_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            chat_id=chat.id,
            is_new_chat=False
        )
    except Exception as e:
        return JsonResponse({'error': f'Quiz generation failed: {str(e)}'}, status=500)

    # Extract only the HTML part
    match = re.search(r'(<div class="quiz-question".*)', quiz_html, re.DOTALL)
    if match:
        quiz_html = match.group(1)

    # Save as a quiz message
    quiz_msg = Message.objects.create(
        chat=chat,
        role='assistant',
        type='quiz',
        quiz_html=quiz_html,
        content=''
    )

    return JsonResponse({'quiz_html': quiz_html, 'message_id': quiz_msg.id})
