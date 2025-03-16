# chat/views.py
from django.http import JsonResponse
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Chat, Message
from groq import Groq  # Import Groq client
import PyPDF2  # Add this import
from django.utils.safestring import mark_safe  # Import mark_safe
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
chat_service = ChatService()

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
                conversation = [{'role': msg.role, 'text': msg.content}
                                for msg in messages]

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
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            prompt_text = request.POST.get('prompt', '').strip()
            uploaded_file = request.FILES.get('file')

            # Process file if present
            file_info, _ = chat_service.process_file(uploaded_file)
            if uploaded_file:
                chat_service.save_file(chat.id, uploaded_file)

            # Combine prompt with file info
            full_prompt = prompt_text + (file_info if file_info else "")

            # Create user message
            chat_service.create_message(chat, 'user', full_prompt)

            # Update chat title if needed
            if chat.title == "New Chat" and prompt_text:
                chat_service.update_chat_title(chat, prompt_text)

            # Get system prompt and prepare messages
            system_prompt = request.session.get('system_prompt', SYSTEM_PROMPT)
            messages = [{"role": "system", "content": system_prompt}]
            chat_history = chat_service.get_chat_history(chat)
            messages.extend([{"role": msg.role, "content": msg.content}
                            for msg in chat_history])
            # Stream response
            return self.stream_response(chat, messages)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def stream_response(self, chat, messages):
        def event_stream():
            try:
                accumulated_response = ""
                stream = chat_service.ai_manager.get_chat_completion(messages)

                for chunk in stream:
                    content = chunk.choices[0].delta.content

                    if content:
                        accumulated_response += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                if accumulated_response:
                    chat_service.create_message(
                        chat, 'assistant', accumulated_response)
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
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

# Add this after your existing view functions


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
