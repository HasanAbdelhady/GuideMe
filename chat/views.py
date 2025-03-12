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

            # Process uploaded file if present
            file_content = ""
            file_info = ""
            if uploaded_file:
                file_name = uploaded_file.name
                file_ext = os.path.splitext(file_name)[1].lower()[
                    1:]  # Get extension without dot

                # Process different file types
                if file_ext == 'pdf':
                    try:
                        pdf_reader = PyPDF2.PdfReader(uploaded_file)
                        file_content = "\n\n".join(
                            page.extract_text() for page in pdf_reader.pages
                        )
                    except Exception as e:
                        file_content = f"Error extracting PDF content: {str(e)}"

                # Handle text-based files
                elif file_ext in ['txt', 'md', 'py', 'js', 'html', 'css', 'json']:
                    try:
                        file_content = uploaded_file.read().decode('utf-8')
                    except UnicodeDecodeError:
                        file_content = "Unable to decode file as text"

                    # Reset file pointer for storage
                    uploaded_file.seek(0)

                # Store file
                file_path = default_storage.save(
                    f'chat_uploads/{chat.id}/{file_name}',
                    uploaded_file
                )

                # Add file information to the prompt
                file_info = f"\n\nI've uploaded a file: {file_name}"
                if file_content:
                    file_info += "\n\nFile content:\n```\n" + \
                        file_content[:20000] + "\n```"
                    if len(file_content) > 20000:
                        file_info += "\n(File content truncated due to length)"

            # Combine prompt text with file info
            full_prompt = prompt_text
            if file_info:
                full_prompt += file_info

            # Create user message in DB
            Message.objects.create(
                chat=chat,
                role='user',
                content=full_prompt
            )

            # Check title and update if it's a new chat
            if chat.title == "New Chat" and prompt_text:
                # Limit title length to avoid very long titles
                title_text = prompt_text[:50] + \
                    ('...' if len(prompt_text) > 50 else '')
                chat.title = title_text
                chat.save()

            # Get system prompt
            system_prompt = request.session.get('system_prompt', SYSTEM_PROMPT)

            # Format conversation history for the API
            messages = []
            # Add system message
            messages.append({"role": "system", "content": system_prompt})

            # Add conversation history (up to 10 most recent messages)
            chat_history = list(
                chat.messages.all().order_by('created_at'))[-10:]
            for msg in chat_history:
                messages.append({"role": msg.role, "content": msg.content})

            # Set up streaming response
            def event_stream():
                try:
                    accumulated_response = ""
                    stream = groq_client.chat.completions.create(
                        model="llama-3.2-90b-vision-preview",
                        messages=messages,
                        temperature=0.7,
                        top_p=1,
                        stream=True,
                    )

                    for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content:
                            accumulated_response += content
                            data = {
                                'content': content,
                                'type': 'content'
                            }
                            yield f"data: {json.dumps(data)}\n\n"

                    if accumulated_response:
                        Message.objects.create(
                            chat=chat,
                            role='assistant',
                            content=accumulated_response
                        )
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"

                except Exception as e:
                    error_msg = str(e)
                    error_data = {
                        'type': 'error',
                        'content': error_msg
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

            # Create streaming response with correct headers
            response = StreamingHttpResponse(
                event_stream(),
                content_type='text/event-stream'
            )
            # Set cache control without connection header
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            
            return response

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@login_required
def create_chat(request):
    if request.method == "POST":
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


def get_system_prompt(user):
    # Define detailed learning style characteristics and strategies
    learning_style_prompts = {
        'visual': {
            'description': 'visual learning through diagrams, charts, and imagery',
            'strategies': [
                'Use diagrams, charts, mind maps, and visual examples',
                'Include color coding and visual hierarchies',
                'Create visual analogies and metaphors',
                'Incorporate infographics and visual summaries'
            ]
        },
        'auditory': {
            'description': 'auditory learning through discussion and verbal explanation',
            'strategies': [
                'Explain concepts conversationally',
                'Use verbal analogies and mnemonics',
                'Incorporate rhythm and patterns in explanations',
                'Suggest audio resources and verbal repetition techniques'
            ]
        },
        'kinesthetic': {
            'description': 'hands-on learning through practical application',
            'strategies': [
                'Provide interactive exercises and practical examples',
                'Include real-world applications and case studies',
                'Suggest hands-on experiments and activities',
                'Break down concepts into step-by-step procedures'
            ]
        },
        'reading': {
            'description': 'reading and writing-based learning',
            'strategies': [
                'Provide detailed written explanations and references',
                'Include text-based summaries and key points',
                'Suggest note-taking strategies and written exercises',
                'Reference academic papers and written resources'
            ]
        }
    }

    # Study time preferences with specific guidelines
    study_time_guidelines = {
        'short': {
            'duration': '25-30 minutes',
            'strategy': 'Break content into small, focused segments with clear learning objectives'
        },
        'medium': {
            'duration': '45-60 minutes',
            'strategy': 'Balance depth and breadth with regular mini-reviews'
        },
        'long': {
            'duration': '90-120 minutes',
            'strategy': 'Provide comprehensive coverage with periodic breaks and synthesis points'
        }
    }

    # Quiz preference interpretations
    quiz_strategies = {
        True: 'Incorporate frequent knowledge checks, interactive quizzes, and self-assessment opportunities throughout the learning process',
        False: 'Include occasional summary questions and gentle comprehension checks to reinforce key concepts'
    }

    # Get active learning styles and their strategies
    active_styles = []
    for style in ['visual', 'auditory', 'kinesthetic', 'reading']:
        if getattr(user, f'learning_style_{style}'):
            active_styles.append(style)

    # Default to balanced approach if no styles selected
    if not active_styles:
        active_styles = ['visual', 'reading']  # Default to common styles

    # Compile learning strategies
    style_strategies = []
    for style in active_styles:
        style_strategies.extend(learning_style_prompts[style]['strategies'])

    # Get study time preference with fallback
    study_time = user.preferred_study_time if user.preferred_study_time else 'medium'
    time_guide = study_time_guidelines[study_time]

    # Determine quiz approach
    quiz_preference = bool(
        user.quiz_preference and int(user.quiz_preference) <= 3)

    # Get interests and custom interests
    interests = [interest.name for interest in user.interests.all()]
    if user.custom_interests:
        custom_interests = [i.strip()
                            for i in user.custom_interests.split(',') if i.strip()]
        interests.extend(custom_interests)

    # Build the comprehensive prompt
    prompt = (
        f"You are an adaptive AI tutor specializing in personalized education. "
        f"Primary learning approach: {', '.join(style.title() for style in active_styles)}. "
        "\n\nLearning Strategies:\n" +
        '\n'.join(f"- {strategy}" for strategy in style_strategies) +
        f"\n\nSession Structure:\n"
        f"- Optimize for {time_guide['duration']} sessions\n"
        f"- {time_guide['strategy']}\n"
        f"- {quiz_strategies[quiz_preference]}\n"
    )

    if interests:
        prompt += (
            f"\nSubject Expertise:\n"
            f"- Primary focus areas: {', '.join(interests)}\n"
            f"- Draw connections between topics when relevant\n"
            f"- Provide field-specific examples and applications"
        )

    prompt += (
        "\n\nAdditional Guidelines:\n"
        "- Adapt explanation complexity based on user understanding\n"
        "- Provide clear learning objectives at the start\n"
        "- Summarize key points at regular intervals\n"
        "- Encourage active participation and critical thinking\n"
        "- Offer additional resources for deeper learning"
    )

    return prompt

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
        Message.objects.create(
            chat=chat,
            role='user',
            text=user_message
        )

        # Get the AI response
        system_prompt = request.session.get('system_prompt', SYSTEM_PROMPT)

        # Prepare conversation history
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add previous messages from this chat for context
        chat_history = Message.objects.filter(chat=chat).order_by('created_at')
        for msg in chat_history:
            messages.append({"role": msg.role, "content": msg.text})

        # Get response from AI
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
            top_p=1,
            stream=False
        )

        # Extract the assistant's message
        assistant_message = response.choices[0].message.content

        # Save the assistant's response to this chat
        Message.objects.create(
            chat=chat,
            role='assistant',
            text=assistant_message
        )

        # Update chat title if this is the first message
        if chat_history.count() <= 2 and not chat.title:
            # Generate a title based on the conversation
            title_prompt = f"User: {user_message}\nAssistant: {assistant_message}\n\nBased on this conversation, generate a very short title (5 words or less)."
            title_response = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": title_prompt}],
                temperature=0.7,
                max_tokens=20,
                stream=False
            )
            chat.title = title_response.choices[0].message.content.strip().strip(
                '"')
            chat.save()

        # Process the response with markdown
        processed_response = mark_safe(html.escape(assistant_message))

        return JsonResponse({
            'response': processed_response,
            'chat_id': chat.id,
            'chat_title': chat.title
        })

    except Exception as e:
        print(f"Error: {str(e)}")
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
def update_system_prompt(request):
    if request.method == 'POST':
        try:
            # Get updated preferences
            prefs = request.user.get_learning_preferences()

            # Update system prompt
            new_prompt = get_system_prompt(request.user)

            # Store updated prompt in session for use in chat
            request.session['system_prompt'] = new_prompt

            return JsonResponse({'success': True})
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
