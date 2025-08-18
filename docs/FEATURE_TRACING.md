# 🔍 Feature Tracing Guide - Post-Login User Features

This document provides a comprehensive trace of each feature available to logged-in users in the MentorAI application, including the actual class names, function names, libraries, and modules used in their implementation.

## 📋 Table of Contents

1. [Main Entry Points After Login](#main-entry-points-after-login)
2. [Feature 1: Chat Message Processing](#feature-1-chat-message-processing)
3. [Feature 2: Diagram Generation](#feature-2-diagram-generation)
4. [Feature 3: YouTube Integration](#feature-3-youtube-integration)
5. [Feature 4: Quiz Generation](#feature-4-quiz-generation)
6. [Feature 5: Flashcard System](#feature-5-flashcard-system)
7. [Feature 6: RAG (Document Context) System](#feature-6-rag-document-context-system)
8. [Feature 7: Study Hub](#feature-7-study-hub)
9. [Feature 8: Chat Management](#feature-8-chat-management)
10. [Feature 9: User Preferences Integration](#feature-9-user-preferences-integration)
11. [Feature 10: Mixed Content Handling](#feature-10-mixed-content-handling)
12. [Key Supporting Services](#key-supporting-services)

---

## 📋 Main Entry Points After Login

### Chat Interface Access
- **URL:** `/chat/new/` or `/chat/<uuid:chat_id>/`  
- **View:** `ChatView` (class-based view)  
- **Template:** `chat/templates/chat/chat.html`  
- **Decorator:** `@method_decorator(login_required, name="dispatch")`

```python
# chat/views.py
@method_decorator(login_required, name="dispatch")
class ChatView(View):
    template_name = "chat/chat.html"
    
    def get(self, request, chat_id=None):
        # Handles both new chat and existing chat loading
        chats = Chat.objects.filter(user=request.user).order_by("-updated_at")
```

---

## 💬 Feature 1: Chat Message Processing

### Core Flow:
1. **Frontend:** `chat/static/chat/js/chat.js`
2. **Backend:** `ChatStreamView.post()` → `ChatAgentSystem.process_message()`
3. **Tools:** Various AI tools via agent system

### Key Classes/Functions:

#### A. Message Submission
```javascript
// chat/static/chat/js/chat.js
document.getElementById("chat-form").addEventListener("submit", function(e) {
    // Form submission handler
    sendMessage(); // Main message sending function
});
```

#### B. Server-Side Processing
```python
# chat/views.py
class ChatStreamView(View):
    async def post(self, request, chat_id):
        # Main message processing endpoint
        user = await request.auser()
        chat = await sync_to_async(Chat.objects.get)(id=chat_id, user=user)
        
        # Extract modes and content
        rag_mode_active = request.POST.get("rag_mode_active", "false").lower() == "true"
        diagram_mode_active = request.POST.get("diagram_mode_active", "false").lower() == "true"
        youtube_mode_active = request.POST.get("youtube_mode_active", "false").lower() == "true"
        
        # Route to agent system
        ai_response, tool_results = await agent_system.process_message(
            user_message=user_message,
            chat_context=chat_context,
            active_modes=active_modes,
        )
```

#### C. Agent System Coordination
```python
# chat/agent_system.py
class ChatAgentSystem:
    def __init__(self, chat_service, ai_service: AIService):
        self.tools: List[BaseTool] = [
            DiagramTool(chat_service),      # Diagram generation
            YouTubeTool(chat_service),      # YouTube integration
            QuizTool(chat_service),         # Quiz creation
            FlashcardTool(ai_service),      # Flashcard generation
        ]
    
    async def process_message(self, user_message, chat_context, active_modes):
        # Tool selection and execution
        tool_results = await self._select_and_execute_tools(...)
        ai_response = await self._get_contextual_ai_response(...)
```

#### D. Tool Selection Algorithm
```python
# chat/agent_system.py
async def _select_and_execute_tools(self, user_message, chat_context, active_modes):
    # Each tool evaluates confidence (0.0-1.0)
    for tool in self.tools:
        confidence = await tool.can_handle(user_message, chat_context)
        if confidence >= self.confidence_threshold:  # 0.5 default
            # Add to execution list
    
    # Execute selected tools in parallel
    tasks = [tool.execute(user_message, chat_context) for tool in selected_tools]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 🎨 Feature 2: Diagram Generation

### Trigger: 
Keywords like "diagram", "visualize", "flowchart", "draw", "show me"

### Implementation Chain:

#### A. Tool Detection
```python
# chat/tools/diagram_tool.py
class DiagramTool(BaseTool):
    @property
    def name(self) -> str:
        return "diagram_generator"
    
    @property
    def triggers(self) -> List[str]:
        return [
            "diagram", "chart", "visualize", "draw", "flowchart",
            "architecture", "process flow", "explain visually"
        ]
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        message_lower = user_message.lower()
        
        # High confidence patterns (0.9)
        high_confidence_patterns = [
            r"(create|make|generate|draw|show)\s+(a\s+)?(diagram|chart|flowchart)",
            r"visualize",
            r"show me (how|the process|the flow|the architecture)",
            r"explain (visually|with a diagram)",
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9
        
        # Medium confidence triggers (0.6)
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.6
        
        return 0.0
```

#### B. Diagram Generation Process
```python
# chat/tools/diagram_tool.py
async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
    try:
        # Generate diagram using chat service
        diagram_id = await self.chat_service.generate_diagram_image(
            chat_history_messages=chat_context.get("messages_for_llm", []),
            user_query=user_message,
            chat_id=chat_context["chat"].id,
            user_id=chat_context["user"].id,
        )
        
        if diagram_id:
            return ToolResult(
                success=True,
                content=f"Diagram generated for: {user_message[:100]}",
                message_type="diagram",
                structured_data={"diagram_image_id": str(diagram_id)},
                metadata={"tool_used": "diagram_generator"},
            )
```

#### C. Image Storage & Serving
```python
# chat/models.py
class DiagramImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="diagram_images")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="diagram_images")
    image_data = models.BinaryField()  # Stores PNG data
    filename = models.CharField(max_length=255, default="diagram.png")
    content_type = models.CharField(max_length=50, default="image/png")
    created_at = models.DateTimeField(auto_now_add=True)

# chat/views.py
@login_required
def serve_diagram_image(request, diagram_id):
    """Serves generated diagram images"""
    diagram_image_instance = get_object_or_404(
        DiagramImage, id=diagram_id, user=request.user
    )
    return HttpResponse(
        diagram_image_instance.image_data,
        content_type=diagram_image_instance.content_type,
    )
```

#### D. Frontend Rendering
```javascript
// chat/static/chat/js/chat.js
if (data.type === 'diagram_image') {
    const diagramId = data.diagram_image_id;
    const imageUrl = `/chat/diagram_image/${diagramId}/`;
    
    // Create image element
    const img = document.createElement('img');
    img.src = imageUrl;
    img.className = 'diagram-image max-w-full h-auto rounded-lg shadow-lg';
    
    // Add to chat interface
    messageContainer.appendChild(img);
}
```

---

## 🎥 Feature 3: YouTube Integration

### Trigger: 
Keywords like "youtube", "video", "tutorial", "watch", "recommend"

### Implementation Chain:

#### A. Tool Detection
```python
# chat/tools/youtube_tool.py
class YouTubeTool(BaseTool):
    @property
    def name(self) -> str:
        return "youtube"
    
    @property
    def triggers(self) -> List[str]:
        return [
            "youtube", "video", "watch", "recommend", "tutorial",
            "learn more", "show me videos", "find videos", "educational content"
        ]
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        message_lower = user_message.lower()
        
        # High confidence patterns (0.9)
        high_confidence_patterns = [
            r"(find|show|recommend|suggest)\s+(me\s+)?(youtube|videos?|tutorials?)",
            r"youtube.*about",
            r"watch.*video",
            r"learn more.*video",
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9
        
        # Medium confidence triggers (0.6)
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.6
        
        # Learning context suggests video might be helpful (0.4)
        learning_keywords = ["learn", "tutorial", "how to", "guide", "instruction"]
        if any(keyword in message_lower for keyword in learning_keywords):
            return 0.4
        
        return 0.0
```

#### B. YouTube Processing
```python
# chat/tools/youtube_tool.py
async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
    try:
        chat_service = chat_context.get("chat_service")
        chat_history = chat_context.get("messages_for_llm", [])
        
        # Get YouTube agent response (summarization or recommendations)
        response = await chat_service.get_youtube_agent_response(
            user_message, chat_history
        )
        
        # Try to parse as JSON for video recommendations
        try:
            video_data = json.loads(response)
            if isinstance(video_data, list) and video_data:
                # This is video recommendation data
                return ToolResult(
                    success=True,
                    content="Here are some YouTube video recommendations:",
                    message_type="youtube",
                    structured_data={"videos": video_data},
                )
        except json.JSONDecodeError:
            # Text response (video summary)
            pass
        
        # Return as text response
        return ToolResult(success=True, content=response, message_type="youtube")
```

#### C. YouTube Agent Service
```python
# chat/agent_tools.py
def extract_youtube_url(text: str):
    """Extract YouTube URL from text"""
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([\w-]+)',
    ]
    # Returns extracted URL or None

def run_youtube_agent(query: str, chat_history: list):
    """Router for YouTube functionality"""
    extracted_url = extract_youtube_url(query)
    
    if extracted_url:
        # Summarize video
        result = summarize_video(extracted_url)
    else:
        # Recommend videos
        result = recommend_videos(query, chat_history)
    
    return result
```

#### D. Frontend Rendering
```javascript
// chat/static/chat/js/chat.js
if (data.type === 'youtube_recommendations') {
    const videoList = data.data;
    
    // Create video recommendation cards
    videoList.forEach(video => {
        const videoCard = document.createElement('div');
        videoCard.className = 'video-card bg-gray-800 rounded-lg p-4 mb-4';
        videoCard.innerHTML = `
            <h3 class="text-lg font-semibold">${video.title}</h3>
            <p class="text-gray-400">${video.description}</p>
            <a href="${video.url}" target="_blank" class="text-blue-400">Watch Video</a>
        `;
        messageContainer.appendChild(videoCard);
    });
}
```

---

## 📝 Feature 4: Quiz Generation

### Trigger: 
Keywords like "quiz", "test", "check understanding", "assess me"

### Implementation Chain:

#### A. Tool Detection
```python
# chat/tools/quiz_tool.py
class QuizTool(BaseTool):
    @property
    def name(self) -> str:
        return "quiz_generator"
    
    @property
    def triggers(self) -> List[str]:
        return [
            "quiz", "test", "question", "practice",
            "check understanding", "assess me", "make questions", "test my knowledge"
        ]
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        message_lower = user_message.lower()
        
        # High confidence patterns (0.9)
        high_confidence_patterns = [
            r"(create|make|generate)\s+(a\s+)?(quiz|test|questions?)",
            r"test\s+(my\s+)?(knowledge|understanding)",
            r"quiz\s+me",
            r"check\s+(my\s+)?understanding",
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, message_lower):
                return 0.9
        
        # Medium confidence triggers (0.7)
        if any(trigger in message_lower for trigger in self.triggers):
            return 0.7
        
        return 0.0
```

#### B. Quiz Generation & Storage
```python
# chat/tools/quiz_tool.py
async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
    try:
        # Generate quiz using chat service
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
            
            return ToolResult(
                success=True,
                content="Here's your interactive quiz:",
                message_type="quiz",
                structured_data={"quiz_html": quiz_data["quiz_html"]},
                metadata={"tool_used": "quiz_generator", "saved_to_question_bank": True},
            )

async def _save_quiz_to_question_bank(self, quiz_data, chat, user_message):
    """Extract and save individual questions to the question bank"""
    from bs4 import BeautifulSoup
    from ..models import ChatQuestionBank
    
    quiz_html = quiz_data.get("quiz_html", "")
    soup = BeautifulSoup(quiz_html, "html.parser")
    question_divs = soup.find_all("div", class_="quiz-question")
    
    for i, div in enumerate(question_divs):
        question_text = div.find("div", class_="font-semibold mb-1").get_text(strip=True)
        correct_answer = div.get("data-correct", "").upper()
        
        # Save to question bank
        await sync_to_async(ChatQuestionBank.objects.create)(
            chat=chat,
            question_html=str(div),
            question_text=question_text,
            correct_answer=correct_answer,
            topic=self._extract_topic_from_message(user_message),
            difficulty="medium",
        )
```

#### C. Quiz Database Models
```python
# chat/models.py
class ChatQuestionBank(models.Model):
    """Store quiz questions from each chat"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="question_bank")
    question_html = models.TextField()  # The full quiz HTML
    question_text = models.TextField()  # Extracted question text for search
    correct_answer = models.CharField(max_length=10)  # A, B, C, D
    topic = models.CharField(max_length=300, blank=True)
    difficulty = models.CharField(
        max_length=20,
        default="medium",
        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
    )
    times_answered = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def success_rate(self):
        if self.times_answered == 0:
            return 0
        return (self.times_correct / self.times_answered) * 100
```

#### D. Manual Quiz Generation
```python
# chat/views.py
@login_required
@require_POST
def chat_quiz(request, chat_id):
    """Manual quiz generation from chat history"""
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    
    if chat.messages.count() < 3:
        return JsonResponse({
            "error": "Not enough conversation content to generate a meaningful quiz."
        }, status=400)
    
    # Get chat history
    history_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in chat.messages.all().order_by("created_at")
    ]
    
    # Generate quiz
    quiz_data = async_to_sync(chat_service.generate_quiz)(
        chat_history_messages=history_messages, chat_id=chat.id
    )
    
    # Save as quiz message
    quiz_msg = Message.objects.create(
        chat=chat,
        role="assistant",
        type="quiz",
        quiz_html=quiz_data.get("quiz_html", ""),
        content="Here is your quiz:",
    )
    
    return JsonResponse({
        "quiz_html": quiz_data.get("quiz_html", ""),
        "message_id": quiz_msg.id
    })
```

#### E. Frontend Quiz Rendering
```javascript
// chat/static/chat/js/chat.js
if (data.type === 'quiz_html') {
    const quizHtml = data.quiz_html;
    
    // Create quiz container
    const quizContainer = document.createElement('div');
    quizContainer.className = 'quiz-container bg-gray-800 rounded-lg p-6 my-4';
    quizContainer.innerHTML = quizHtml;
    
    // Initialize quiz form handlers
    initializeQuizForms(quizContainer);
    messageContainer.appendChild(quizContainer);
}

function initializeQuizForms(parentElement) {
    const quizForms = parentElement.querySelectorAll('.quiz-form');
    quizForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Check answers and provide feedback
            const formData = new FormData(form);
            const selectedAnswer = formData.get('answer');
            const correctAnswer = form.dataset.correct;
            
            // Show feedback
            const feedbackDiv = form.querySelector('.quiz-feedback');
            if (selectedAnswer === correctAnswer) {
                feedbackDiv.textContent = "Correct! Well done.";
                feedbackDiv.className = "quiz-feedback mt-1.5 text-green-400";
            } else {
                feedbackDiv.textContent = `Incorrect. The correct answer is ${correctAnswer}.`;
                feedbackDiv.className = "quiz-feedback mt-1.5 text-red-400";
            }
        });
    });
}
```

---

## 🗂️ Feature 5: Flashcard System

### Trigger: 
Keywords like "flashcard", "study", "memorize", or automatic generation from important concepts

### Implementation Chain:

#### A. Tool Detection
```python
# chat/tools/flashcard_tool.py
class FlashcardTool(BaseTool):
    def __init__(self, ai_service):
        self.ai_service = ai_service
        # Uses Gemini model specifically for flashcard generation
        try:
            FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
            if FLASHCARD_API_KEY:
                genai.configure(api_key=FLASHCARD_API_KEY)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            else:
                self.gemini_model = None
        except Exception as e:
            self.gemini_model = None
    
    @property
    def triggers(self) -> List[str]:
        return [
            "flashcard", "flashcards", "study cards", "memorize", "review cards",
            "study", "learn", "remember", "key concepts", "important terms"
        ]
    
    async def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
        if not self.gemini_model:
            return 0.0
        
        message_lower = user_message.lower()
        
        # High confidence for explicit flashcard requests (0.9)
        if any(word in message_lower for word in ["flashcard", "study card", "memorize"]):
            return 0.9
        
        # Medium confidence for study-related terms (0.6)
        study_keywords = ["study", "learn", "review", "remember", "key concepts"]
        if any(keyword in message_lower for keyword in study_keywords):
            return 0.6
        
        # Auto-generate for content-rich conversations (0.4)
        chat_history = chat_context.get("messages_for_llm", [])
        if len(chat_history) >= 4:  # Sufficient content for flashcards
            return 0.4
        
        return 0.0
```

#### B. Flashcard Generation Process
```python
# chat/tools/flashcard_tool.py
async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
    try:
        if not self.gemini_model:
            return ToolResult(success=False, error="Flashcard generation not available")
        
        chat_history = chat_context.get("messages_for_llm", [])
        chat = chat_context["chat"]
        
        # Extract key concepts from conversation history
        key_concepts = self._extract_key_concepts_from_history(chat_history)
        
        if not key_concepts:
            return ToolResult(success=False, error="No suitable concepts found for flashcards")
        
        # Generate flashcards using Gemini
        flashcard_data = await self._generate_flashcards_with_gemini(key_concepts)
        
        if flashcard_data:
            # Save flashcards to database
            saved_count = await self._save_flashcards_to_database(flashcard_data, chat)
            
            return ToolResult(
                success=True,
                content=f"Generated {saved_count} flashcards from our conversation! Check your Study Hub to review them.",
                message_type="flashcard_update",
                structured_data={"flashcards_created": saved_count},
                metadata={"tool_used": "flashcard_generator", "concepts_processed": len(key_concepts)},
            )

def _extract_key_concepts_from_history(self, chat_history: List[Dict]) -> List[str]:
    """Extract important concepts, terms, and definitions from chat history"""
    concepts = []
    
    for message in chat_history:
        if message.get("role") == "assistant":
            content = message.get("content", "")
            
            # Look for definition patterns
            definition_patterns = [
                r"(.+?)\s+(?:is|are|means?|refers? to|defined as)\s+(.+?)(?:\.|$)",
                r"(.+?):\s*(.+?)(?:\.|$)",
                r"The term\s+(.+?)\s+(.+?)(?:\.|$)",
            ]
            
            for pattern in definition_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    term = match.group(1).strip()
                    definition = match.group(2).strip()
                    
                    # Filter out common words and short terms
                    if (len(term) > 3 and len(definition) > 10 and 
                        term.lower() not in self.stop_words):
                        concepts.append(f"{term}: {definition}")
    
    return concepts[:10]  # Limit to top 10 concepts

async def _generate_flashcards_with_gemini(self, key_concepts: List[str]) -> List[Dict]:
    """Generate flashcards using Gemini model"""
    concepts_text = "\n".join(key_concepts)
    
    prompt = f"""Based on these key concepts from a learning conversation, create flashcards for studying:

{concepts_text}

Create flashcards in this exact format:
Term: [Clear, concise term or concept]
Definition: [Accurate, helpful definition or explanation]

Rules:
- One flashcard per line
- Use "Term: Definition" format exactly
- Keep definitions concise but complete
- Focus on the most important concepts
- Maximum 8 flashcards

Generate flashcards now:"""
    
    try:
        response = await sync_to_async(self.gemini_model.generate_content)(prompt)
        flashcard_text = response.text.strip()
        
        # Parse flashcard response
        flashcards = []
        for line in flashcard_text.splitlines():
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    term = parts[0].strip()
                    definition = parts[1].strip()
                    if term and definition:
                        flashcards.append({"term": term, "definition": definition})
        
        return flashcards
    except Exception as e:
        logger.error(f"Gemini flashcard generation failed: {e}")
        return []
```

#### C. Flashcard Database Storage
```python
# chat/models.py
class ChatFlashcard(models.Model):
    """Store flashcards for each chat"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="flashcards")
    term = models.CharField(max_length=200)
    definition = models.TextField()
    context = models.TextField(blank=True)  # Context from conversation
    auto_generated = models.BooleanField(default=False)  # AI-generated vs user-created
    created_at = models.DateTimeField(auto_now_add=True)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    confidence_level = models.IntegerField(default=0)  # 0-5 scale for spaced repetition
    
    class Meta:
        unique_together = ["chat", "term"]
        ordering = ["-created_at"]

# chat/tools/flashcard_tool.py
async def _save_flashcards_to_database(self, flashcard_data: List[Dict], chat) -> int:
    """Save generated flashcards to database"""
    from ..models import ChatFlashcard
    
    saved_count = 0
    for flashcard in flashcard_data:
        try:
            # Check if flashcard already exists
            existing = await sync_to_async(
                ChatFlashcard.objects.filter(
                    chat=chat, term=flashcard["term"]
                ).first
            )()
            
            if not existing:
                await sync_to_async(ChatFlashcard.objects.create)(
                    chat=chat,
                    term=flashcard["term"],
                    definition=flashcard["definition"],
                    auto_generated=True,
                    context="Generated from conversation",
                )
                saved_count += 1
        except Exception as e:
            logger.error(f"Error saving flashcard: {e}")
            continue
    
    return saved_count
```

#### D. Standalone Flashcard Generator
```python
# chat/views.py
@csrf_exempt
def generate_flashcards_view(request):
    """Standalone flashcard generation endpoint"""
    if request.method == "POST":
        if not flashcard_model:  # Global Gemini model
            return JsonResponse({"error": "Flashcard generation not configured."}, status=500)
        
        try:
            data = json.loads(request.body)
            topic = data.get("topic", "").strip()
            
            if not topic:
                return JsonResponse({"error": "Topic is required."}, status=400)
            
            # Generate flashcards for topic
            prompt = f"""Generate flashcards for the topic: "{topic}". 
            Format: Term: Definition (one per line)
            Example:
            Neural Network: A computing system inspired by biological neural networks
            Gradient Descent: An optimization algorithm used to minimize cost functions"""
            
            response = flashcard_model.generate_content(prompt)
            flashcard_text = response.text.strip()
            
            # Parse response into flashcard objects
            flashcards = []
            for line in flashcard_text.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        term = parts[0].strip()
                        definition = parts[1].strip()
                        if term and definition:
                            flashcards.append({"term": term, "definition": definition})
            
            return JsonResponse({"flashcards": flashcards})
            
        except Exception as e:
            return JsonResponse({"error": f"Flashcard generation failed: {str(e)}"}, status=500)
    
    # GET request - render flashcard generation page
    return render(request, "chat/flashcards.html")
```

---

## 📁 Feature 6: RAG (Document Context) System

### Activation: 
RAG mode toggle + file uploads for document-based conversations

### Implementation Chain:

#### A. File Management Interface
```python
# chat/views.py
@method_decorator(login_required, name="dispatch")
class ChatRAGFilesView(View):
    """Handle RAG file uploads and management"""
    
    def get(self, request, chat_id):
        """List RAG files for a chat"""
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            rag_files = chat.rag_files.all().order_by("-uploaded_at")
            files_data = [
                {"id": str(rag_file.id), "name": rag_file.original_filename}
                for rag_file in rag_files
            ]
            return JsonResponse(files_data, safe=False)
        except Exception as e:
            return JsonResponse({"error": "Could not retrieve RAG files."}, status=500)
    
    def post(self, request, chat_id):
        """Upload new RAG file"""
        MAX_RAG_FILES = 10
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            
            if chat.rag_files.count() >= MAX_RAG_FILES:
                return JsonResponse({"error": f"RAG file limit ({MAX_RAG_FILES}) reached."}, status=400)
            
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                return JsonResponse({"error": "No file provided."}, status=400)
            
            # Validate file type
            allowed_extensions = [".pdf", ".txt"]
            file_name, file_extension = os.path.splitext(uploaded_file.name)
            if file_extension.lower() not in allowed_extensions:
                return JsonResponse({"error": "Only PDF and TXT files are allowed."}, status=400)
            
            # Create RAG file record
            rag_file = ChatRAGFile(
                chat=chat,
                user=request.user,
                file=uploaded_file,
                original_filename=uploaded_file.name,
            )
            rag_file.save()
            
            # Clear existing vector index to force rebuild
            DocumentChunk.objects.filter(chat_id=chat_id).delete()
            ChatVectorIndex.objects.filter(chat_id=chat_id).delete()
            
            return JsonResponse({
                "success": True,
                "file": {"id": str(rag_file.id), "name": rag_file.original_filename},
            }, status=201)
            
        except Exception as e:
            return JsonResponse({"error": "Could not upload RAG file."}, status=500)
    
    def delete(self, request, chat_id, file_id):
        """Delete RAG file"""
        try:
            chat = Chat.objects.get(id=chat_id, user=request.user)
            rag_file = ChatRAGFile.objects.get(id=file_id, chat=chat, user=request.user)
            
            # Delete file from storage
            if rag_file.file and default_storage.exists(rag_file.file.name):
                default_storage.delete(rag_file.file.name)
            
            # Delete database record
            rag_file.delete()
            
            # Clear and rebuild vector index
            DocumentChunk.objects.filter(chat_id=chat_id).delete()
            ChatVectorIndex.objects.filter(chat_id=chat_id).delete()
            
            return JsonResponse({"success": True, "message": "File removed successfully."})
            
        except Exception as e:
            return JsonResponse({"error": "Could not delete RAG file."}, status=500)
```

#### B. RAG Database Models
```python
# chat/models.py
def rag_file_upload_path(instance, filename):
    """Define upload path for RAG files"""
    return f"rag_files/user_{instance.user.id}/chat_{instance.chat.id}/{filename}"

class ChatRAGFile(models.Model):
    """Store uploaded documents for RAG"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="rag_files")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    file = models.FileField(upload_to=rag_file_upload_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-uploaded_at"]
        unique_together = [["chat", "original_filename"]]

class DocumentChunk(models.Model):
    """Store document chunks with vector embeddings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="document_chunks")
    rag_file = models.ForeignKey(ChatRAGFile, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()  # Text content of chunk
    chunk_index = models.IntegerField()  # Position in original document
    embedding = VectorField(dimensions=384)  # pgvector field for embeddings
    metadata = models.JSONField(default=dict)  # Additional chunk metadata
    created_at = models.DateTimeField(auto_now_add=True)

class ChatVectorIndex(models.Model):
    """Track vector index status for chats"""
    chat = models.OneToOneField(Chat, on_delete=models.CASCADE, related_name="vector_index")
    total_chunks = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    embedding_model = models.CharField(max_length=100, default="all-MiniLM-L6-v2")
```

#### C. RAG Pipeline Processing
```python
# chat/rag.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_huggingface.embeddings import HuggingFaceEndpointEmbeddings
from pdfminer.high_level import extract_text
from pgvector.django import CosineDistance

class RAG_pipeline:
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model_name
        
        # Use HuggingFace Inference API for embeddings
        api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        model_id = f"sentence-transformers/{embedding_model_name}"
        
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model=model_id,
            task="feature-extraction",
            huggingfacehub_api_token=api_token,
        )
    
    def build_index(self, file_paths_and_types, chat_id=None, rag_files_map=None):
        """Build vector index from uploaded documents"""
        from .models import Chat, ChatVectorIndex, DocumentChunk
        
        chat = Chat.objects.get(id=chat_id)
        
        # Clear existing chunks
        DocumentChunk.objects.filter(chat=chat).delete()
        
        # Process each file
        all_loaded_docs = []
        for file_path, file_type in file_paths_and_types:
            if file_type == "pdf":
                # Extract text from PDF
                text = extract_text(file_path)
                if text and text.strip():
                    doc = Document(
                        page_content=text,
                        metadata={"source": os.path.basename(file_path), "file_path": file_path}
                    )
                    all_loaded_docs.append(doc)
            
            elif file_type == "txt":
                # Load text file
                loader = TextLoader(file_path, encoding="utf-8")
                loaded_docs = loader.load()
                for doc in loaded_docs:
                    doc.metadata["file_path"] = file_path
                all_loaded_docs.extend(loaded_docs)
        
        if not all_loaded_docs:
            return
        
        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_documents(all_loaded_docs)
        
        # Generate embeddings for all chunks
        chunk_texts = [chunk.page_content for chunk in chunks]
        embeddings_list = self.embeddings.embed_documents(chunk_texts)
        
        # Store chunks with embeddings in PostgreSQL
        chunk_objects = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
            # Find corresponding RAG file
            file_path = chunk.metadata.get("file_path", "")
            rag_file = rag_files_map.get(file_path) if rag_files_map else None
            
            if rag_file:
                chunk_obj = DocumentChunk(
                    chat=chat,
                    rag_file=rag_file,
                    content=chunk.page_content,
                    chunk_index=i,
                    embedding=embedding,
                    metadata=chunk.metadata,
                )
                chunk_objects.append(chunk_obj)
        
        # Bulk create chunks
        DocumentChunk.objects.bulk_create(chunk_objects, batch_size=100)
        
        # Update vector index record
        ChatVectorIndex.objects.update_or_create(
            chat=chat,
            defaults={
                "total_chunks": len(chunk_objects),
                "embedding_model": self.embedding_model_name,
            },
        )
    
    def retrieve_docs(self, query: str, chat_id=None):
        """Retrieve relevant documents using vector similarity search"""
        if not chat_id:
            return []
        
        from .models import DocumentChunk
        
        # Generate embedding for query
        query_embedding = self.embeddings.embed_query(query)
        
        # Perform vector similarity search using PostgreSQL + pgvector
        chunks = (
            DocumentChunk.objects.filter(chat_id=chat_id)
            .annotate(similarity=CosineDistance("embedding", query_embedding))
            .order_by("similarity")[:4]  # Get top 4 most similar chunks
        )
        
        # Convert to LangChain Document format
        documents = []
        for chunk in chunks:
            doc = Document(
                page_content=chunk.content,
                metadata={
                    "source": chunk.metadata.get("source", "unknown"),
                    "chunk_index": chunk.chunk_index,
                    "similarity_score": float(chunk.similarity),
                    **chunk.metadata,
                },
            )
            documents.append(doc)
        
        return documents
```

#### D. RAG Query Processing
```python
# chat/views.py - ChatStreamView
if rag_mode_active:
    # RAG mode is active - build index from persisted files
    active_rag_files = await sync_to_async(list)(
        chat.rag_files.filter(user=user).all().order_by("-uploaded_at")
    )
    
    if active_rag_files:
        file_paths_and_types_for_rag = []
        rag_files_map = {}
        
        for rag_file_entry in active_rag_files:
            file_path = rag_file_entry.file.path
            _, file_ext = os.path.splitext(rag_file_entry.original_filename)
            file_type = file_ext.lower().strip(".")
            
            if file_type in ["pdf", "txt"]:
                file_paths_and_types_for_rag.append((file_path, file_type))
                rag_files_map[file_path] = rag_file_entry
        
        if file_paths_and_types_for_rag:
            # Build RAG index
            files_rag_instance = RAG_pipeline()
            await sync_to_async(files_rag_instance.build_index)(
                file_paths_and_types_for_rag,
                chat_id=chat_id,
                rag_files_map=rag_files_map,
            )
            
            # Process query with RAG context (bypass agent system)
            stream = await chat_service.stream_completion(
                messages=messages_for_llm,
                query=user_typed_prompt,
                files_rag=files_rag_instance,
                max_tokens=7000,
                chat_id=chat.id,
            )
            
            # Stream RAG response directly
            accumulated_response = ""
            for chunk in stream:
                content = getattr(chunk.choices[0].delta, "content", None)
                if content:
                    accumulated_response += content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
            
            # Save RAG response to database
            await sync_to_async(Message.objects.create)(
                chat=chat,
                role="assistant",
                content=accumulated_response,
            )
```

#### E. Frontend RAG Interface
```javascript
// chat/static/chat/js/chat.js
// RAG Mode Toggle
const ragToggleButton = document.getElementById("rag-mode-toggle");
const manageRagContextBtn = document.getElementById("manage-rag-context-btn");

ragToggleButton.addEventListener("click", function() {
    isRAGActive = !isRAGActive;
    localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
    
    // Update UI
    if (isRAGActive) {
        ragToggleButton.classList.add("bg-green-600");
        ragToggleButton.textContent = "RAG: ON";
        manageRagContextBtn.classList.remove("hidden");
    } else {
        ragToggleButton.classList.remove("bg-green-600");
        ragToggleButton.textContent = "RAG: OFF";
        manageRagContextBtn.classList.add("hidden");
    }
});

// RAG File Management Modal
manageRagContextBtn.addEventListener("click", function() {
    openRAGModal();
});

function openRAGModal() {
    // Create and show file management modal
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-gray-800 rounded-lg p-6 w-96 max-w-full">
            <h3 class="text-lg font-semibold mb-4">Manage RAG Context Files</h3>
            <div id="rag-files-list" class="mb-4"></div>
            <input type="file" id="rag-file-input" accept=".pdf,.txt" class="hidden">
            <button id="upload-rag-file" class="bg-blue-600 text-white px-4 py-2 rounded mr-2">
                Upload File
            </button>
            <button id="close-rag-modal" class="bg-gray-600 text-white px-4 py-2 rounded">
                Close
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Load existing files
    loadRAGFiles();
    
    // Event handlers
    document.getElementById('upload-rag-file').addEventListener('click', function() {
        document.getElementById('rag-file-input').click();
    });
    
    document.getElementById('rag-file-input').addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            uploadRAGFile(e.target.files[0]);
        }
    });
    
    document.getElementById('close-rag-modal').addEventListener('click', function() {
        document.body.removeChild(modal);
    });
}

function loadRAGFiles() {
    const chatId = getCurrentChatId();
    fetch(`/chat/${chatId}/rag-files/`)
        .then(response => response.json())
        .then(files => {
            const filesList = document.getElementById('rag-files-list');
            filesList.innerHTML = '';
            
            files.forEach(file => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'flex justify-between items-center py-2 border-b border-gray-600';
                fileDiv.innerHTML = `
                    <span class="text-sm">${file.name}</span>
                    <button class="text-red-400 hover:text-red-300 text-sm" 
                            onclick="deleteRAGFile('${file.id}')">Delete</button>
                `;
                filesList.appendChild(fileDiv);
            });
        })
        .catch(error => console.error('Error loading RAG files:', error));
}

function uploadRAGFile(file) {
    const chatId = getCurrentChatId();
    const formData = new FormData();
    formData.append('file', file);
    
    fetch(`/chat/${chatId}/rag-files/`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadRAGFiles(); // Refresh file list
            showNotification('File uploaded successfully!', 'success');
        } else {
            showNotification(data.error || 'Upload failed', 'error');
        }
    })
    .catch(error => {
        console.error('Error uploading file:', error);
        showNotification('Upload failed', 'error');
    });
}
```

---

## 📚 Feature 7: Study Hub

### Access: 
`/chat/<chat_id>/study/` - Centralized study materials for each chat

### Implementation:

#### A. Study Hub View
```python
# chat/views.py
@login_required
def study_hub_view(request, chat_id):
    """Display study hub with flashcards and question bank"""
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    
    # Get all flashcards for this chat
    flashcards = chat.flashcards.all().order_by("created_at")
    
    # Get all questions from question bank
    questions = chat.question_bank.all().order_by("created_at")
    
    context = {
        "chat": chat,
        "flashcards": flashcards,
        "questions": questions,
    }
    return render(request, "chat/study_hub.html", context)
```

#### B. Study Hub Template Structure
```html
<!-- chat/templates/chat/study_hub.html -->
<div class="study-hub-container">
    <h1>Study Hub for: {{ chat.title }}</h1>
    
    <!-- Flashcards Section -->
    <div class="flashcards-section">
        <h2>Flashcards ({{ flashcards.count }})</h2>
        {% for flashcard in flashcards %}
        <div class="flashcard-item" data-id="{{ flashcard.id }}">
            <div class="flashcard-front">
                <h3>{{ flashcard.term }}</h3>
            </div>
            <div class="flashcard-back hidden">
                <p>{{ flashcard.definition }}</p>
                <div class="flashcard-meta">
                    <span>Reviewed: {{ flashcard.review_count }} times</span>
                    <span>Confidence: {{ flashcard.confidence_level }}/5</span>
                </div>
            </div>
            <div class="flashcard-actions">
                <button onclick="flipFlashcard({{ flashcard.id }})">Flip</button>
                <button onclick="markConfidence({{ flashcard.id }}, 1)">Hard</button>
                <button onclick="markConfidence({{ flashcard.id }}, 3)">Medium</button>
                <button onclick="markConfidence({{ flashcard.id }}, 5)">Easy</button>
            </div>
        </div>
        {% endfor %}
    </div>
    
    <!-- Question Bank Section -->
    <div class="questions-section">
        <h2>Question Bank ({{ questions.count }})</h2>
        {% for question in questions %}
        <div class="question-item">
            <div class="question-content">
                {{ question.question_html|safe }}
            </div>
            <div class="question-stats">
                <span>Topic: {{ question.topic }}</span>
                <span>Difficulty: {{ question.difficulty }}</span>
                <span>Success Rate: {{ question.success_rate }}%</span>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
```

#### C. Study Hub JavaScript Interactions
```javascript
// Study Hub functionality
function flipFlashcard(flashcardId) {
    const flashcard = document.querySelector(`[data-id="${flashcardId}"]`);
    const front = flashcard.querySelector('.flashcard-front');
    const back = flashcard.querySelector('.flashcard-back');
    
    if (front.classList.contains('hidden')) {
        front.classList.remove('hidden');
        back.classList.add('hidden');
    } else {
        front.classList.add('hidden');
        back.classList.remove('hidden');
    }
}

function markConfidence(flashcardId, confidence) {
    // Update flashcard confidence and review count
    fetch(`/chat/flashcard/${flashcardId}/review/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            confidence: confidence
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update UI with new stats
            updateFlashcardStats(flashcardId, data.stats);
        }
    });
}

function updateFlashcardStats(flashcardId, stats) {
    const flashcard = document.querySelector(`[data-id="${flashcardId}"]`);
    const metaDiv = flashcard.querySelector('.flashcard-meta');
    metaDiv.innerHTML = `
        <span>Reviewed: ${stats.review_count} times</span>
        <span>Confidence: ${stats.confidence_level}/5</span>
    `;
}
```

---

## ⚙️ Feature 8: Chat Management

### A. Chat Creation
```python
# chat/views.py
@login_required
def create_chat(request):
    """Create a new chat with initial message"""
    if request.method == "POST":
        # Get system prompt for user
        new_prompt = PreferenceService.get_system_prompt(request.user)
        request.session["system_prompt"] = new_prompt
        
        message = request.POST.get("prompt", "").strip()
        
        if not message:
            return JsonResponse({"success": False, "error": "No message provided"}, status=400)
        
        try:
            # Create new chat
            chat = Chat.objects.create(
                user=request.user,
                title=message[:30] + "..." if len(message) > 30 else message,
            )
            
            # Create initial user message
            Message.objects.create(chat=chat, content=message.strip(), role="user")
            
            return JsonResponse({
                "success": True,
                "chat_id": chat.id,
                "redirect_url": f"/chat/{chat.id}/",
                "title": chat.title,
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)
    
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)
```

#### B. Chat Operations
```python
# chat/views.py
@login_required
def delete_chat(request, chat_id):
    """Delete a chat and all its messages"""
    if request.method == "POST":
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            chat.delete()  # Cascade deletes messages, RAG files, etc.
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def update_chat_title(request, chat_id):
    """Update chat title"""
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
    """Clear all messages from a chat"""
    if request.method == "POST":
        try:
            chat = get_object_or_404(Chat, id=chat_id, user=request.user)
            # Delete all messages but keep the chat
            Message.objects.filter(chat=chat).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method not allowed"}, status=405)
```

#### C. Message Editing
```python
# chat/views.py
@login_required
@require_POST
def edit_message(request, chat_id, message_id):
    """Edit a user message and delete subsequent messages"""
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        message_to_edit = get_object_or_404(Message, id=message_id, chat=chat)
        
        # Only allow editing user messages
        if message_to_edit.role != "user":
            return JsonResponse({"error": "Only user messages can be edited."}, status=403)
        
        data = json.loads(request.body)
        new_content = data.get("new_content", "").strip()
        
        if not new_content:
            return JsonResponse({"error": "New content cannot be empty."}, status=400)
        
        # Update the message
        message_to_edit.content = new_content
        message_to_edit.is_edited = True
        message_to_edit.edited_at = timezone.now()
        message_to_edit.save()
        
        # Delete all messages that came after this one
        Message.objects.filter(
            chat=chat, created_at__gt=message_to_edit.created_at
        ).delete()
        
        return JsonResponse({
            "success": True,
            "edited_message_id": message_to_edit.id,
            "new_content": message_to_edit.content,
            "is_edited": message_to_edit.is_edited,
            "edited_at": message_to_edit.edited_at.isoformat() if message_to_edit.edited_at else None,
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Could not edit message: {str(e)}"}, status=500)
```

#### D. Frontend Chat Management
```javascript
// chat/static/chat/js/chat.js
// Chat deletion
function deleteChat(chatId) {
    if (!confirm('Are you sure you want to delete this chat?')) {
        return;
    }
    
    fetch(`/chat/${chatId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Remove chat from sidebar and redirect
            document.querySelector(`[data-chat-id="${chatId}"]`).remove();
            window.location.href = '/chat/new/';
        }
    })
    .catch(error => console.error('Error deleting chat:', error));
}

// Chat title editing
function editChatTitle(chatId, currentTitle) {
    const newTitle = prompt('Enter new chat title:', currentTitle);
    if (newTitle && newTitle.trim() !== currentTitle) {
        fetch(`/chat/${chatId}/update-title/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ title: newTitle.trim() })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update title in UI
                document.querySelector(`[data-chat-id="${chatId}"] .chat-title`).textContent = newTitle;
            }
        });
    }
}

// Message editing
function editMessage(messageId, currentContent) {
    const newContent = prompt('Edit your message:', currentContent);
    if (newContent && newContent.trim() !== currentContent) {
        const chatId = getCurrentChatId();
        
        fetch(`/chat/${chatId}/message/${messageId}/edit/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ new_content: newContent.trim() })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update message in UI and remove subsequent messages
                updateMessageInUI(data);
                removeSubsequentMessages(messageId);
            } else {
                alert(data.error);
            }
        });
    }
}
```

---

## 🎯 Feature 9: User Preferences Integration

### System Prompt Generation:
```python
# chat/preference_service.py
class PreferenceService:
    @staticmethod
    def get_system_prompt(user):
        """Generate personalized system prompt based on user preferences"""
        
        # Get user learning preferences
        preferences = user.get_learning_preferences()
        
        # Base system prompt
        base_prompt = """You are MentorAI, an intelligent learning assistant designed to provide personalized educational support."""
        
        # Learning style adaptations
        learning_styles = preferences["learning_styles"]
        style_adaptations = []
        
        if learning_styles["visual"]:
            style_adaptations.append(
                "Use visual descriptions, diagrams, and structured formatting. "
                "Suggest creating visual aids when explaining complex concepts."
            )
        
        if learning_styles["auditory"]:
            style_adaptations.append(
                "Provide clear verbal explanations and suggest discussing concepts aloud. "
                "Use analogies and storytelling techniques."
            )
        
        if learning_styles["kinesthetic"]:
            style_adaptations.append(
                "Suggest hands-on activities, practical exercises, and real-world applications. "
                "Encourage learning through doing and experimentation."
            )
        
        if learning_styles["reading"]:
            style_adaptations.append(
                "Provide detailed written explanations, reading recommendations, and note-taking strategies. "
                "Structure information clearly with headings and bullet points."
            )
        
        # Study time preferences
        study_time = preferences["study_time"]
        if study_time == "short":
            time_adaptation = "Keep explanations concise and break complex topics into small, digestible chunks."
        elif study_time == "long":
            time_adaptation = "Provide comprehensive, in-depth explanations with detailed examples and context."
        else:  # medium
            time_adaptation = "Balance detail with brevity, providing thorough but focused explanations."
        
        # Quiz preferences
        quiz_pref = preferences.get("quiz_preference", 3)
        if quiz_pref >= 4:
            quiz_adaptation = "Regularly offer quizzes and assessments to reinforce learning."
        elif quiz_pref <= 2:
            quiz_adaptation = "Focus on explanations rather than testing; use quizzes sparingly."
        else:
            quiz_adaptation = "Occasionally suggest quizzes when they would be particularly helpful."
        
        # User interests
        interests = preferences.get("interests", [])
        if interests:
            interest_adaptation = f"When possible, relate concepts to the user's interests: {', '.join(interests)}."
        else:
            interest_adaptation = ""
        
        # Combine all adaptations
        adaptations = [
            *style_adaptations,
            time_adaptation,
            quiz_adaptation,
            interest_adaptation,
        ]
        
        # Build final system prompt
        system_prompt = f"{base_prompt}\n\n"
        system_prompt += "Adapt your teaching style based on these user preferences:\n"
        system_prompt += "\n".join(f"- {adaptation}" for adaptation in adaptations if adaptation)
        system_prompt += "\n\nAlways be encouraging, patient, and supportive in your responses."
        
        return system_prompt
```

### Usage in Chat Processing:
```python
# chat/views.py - ChatStreamView
# Generate personalized system prompt
system_prompt_text = await sync_to_async(PreferenceService.get_system_prompt)(user)
messages_for_llm = [{"role": "system", "content": system_prompt_text}]

# Add chat history
for msg_data in chat_history_db:
    messages_for_llm.append({"role": msg_data.role, "content": msg_data.content})

# Add current user message
messages_for_llm.append({"role": "user", "content": llm_query_content})
```

---

## 📊 Feature 10: Mixed Content Handling

### When Multiple Tools Trigger Simultaneously:

#### A. Mixed Content Detection
```python
# chat/views.py - ChatStreamView
# Get tool results from agent system
ai_response, tool_results = await agent_system.process_message(...)

# Separate successful tools from background processes
primary_tools_used = [
    r for r in tool_results 
    if r.message_type not in ["background_process"] and r.success
]

# Handle multiple tools
if len(primary_tools_used) > 1:
    # Signal mixed content to frontend
    yield f"data: {json.dumps({'type': 'mixed_content_start'})}\n\n"
    
    # Create mixed content message in database
    await self._handle_mixed_content_message(chat, primary_tools_used, ai_response)
    
    # Stream each tool result separately in execution order
    for i, tool_result in enumerate(primary_tools_used):
        if tool_result.message_type == "diagram":
            diagram_image_id = tool_result.structured_data.get("diagram_image_id")
            yield f"data: {json.dumps({
                'type': 'diagram_image', 
                'diagram_image_id': str(diagram_image_id),
                'text_content': tool_result.content,
                'order': getattr(tool_result, 'execution_order', i)
            })}\n\n"
        
        elif tool_result.message_type == "youtube":
            if tool_result.structured_data and "videos" in tool_result.structured_data:
                video_list = tool_result.structured_data.get("videos", [])
                yield f"data: {json.dumps({
                    'type': 'youtube_recommendations',
                    'data': video_list,
                    'order': getattr(tool_result, 'execution_order', i)
                })}\n\n"
        
        elif tool_result.message_type == "quiz":
            quiz_html = tool_result.structured_data.get("quiz_html", "")
            yield f"data: {json.dumps({
                'type': 'quiz_html',
                'quiz_html': quiz_html,
                'order': getattr(tool_result, 'execution_order', i)
            })}\n\n"
```

#### B. Mixed Content Database Storage
```python
# chat/views.py
async def _handle_mixed_content_message(self, chat, tool_results, ai_response):
    """Create a single message that combines multiple tool results"""
    try:
        # Create mixed content structure
        mixed_content_structure = {"type": "mixed", "components": []}
        
        # Set flags for different content types
        has_diagram = False
        has_youtube = False
        has_quiz = False
        has_code = False
        diagram_image_id = None
        quiz_html = ""
        youtube_videos = None
        
        # Process each tool result
        for tool_result in tool_results:
            component = {
                "type": tool_result.message_type,
                "content": tool_result.content,
                "order": getattr(tool_result, "execution_order", len(mixed_content_structure["components"])),
            }
            
            if tool_result.message_type == "diagram":
                has_diagram = True
                diagram_image_id = tool_result.structured_data.get("diagram_image_id")
                component["diagram_image_id"] = str(diagram_image_id) if diagram_image_id else None
            
            elif tool_result.message_type == "youtube":
                has_youtube = True
                if tool_result.structured_data and "videos" in tool_result.structured_data:
                    youtube_videos = tool_result.structured_data.get("videos", [])
                    component["videos"] = youtube_videos
            
            elif tool_result.message_type == "quiz":
                has_quiz = True
                quiz_html = tool_result.structured_data.get("quiz_html", "")
                component["quiz_html"] = quiz_html
            
            # Check for code content
            if any(keyword in tool_result.content.lower() for keyword in ["def ", "function", "import ", "class ", "```"]):
                has_code = True
            
            mixed_content_structure["components"].append(component)
        
        # Add AI response
        if ai_response:
            mixed_content_structure["ai_response"] = ai_response
        
        # Create database message
        message_content = ai_response if ai_response else "Here are your requested resources:"
        
        await sync_to_async(Message.objects.create)(
            chat=chat,
            role="assistant",
            content=message_content,
            type="mixed",
            structured_content=youtube_videos,  # Only YouTube data
            mixed_content_data=mixed_content_structure,  # Full mixed structure
            quiz_html=quiz_html if has_quiz else "",
            diagram_image_id=diagram_image_id if has_diagram else None,
            has_diagram=has_diagram,
            has_youtube=has_youtube,
            has_quiz=has_quiz,
            has_code=has_code,
        )
        
    except Exception as e:
        logger.error(f"Error creating mixed content message: {e}")
        # Fallback to individual messages
        await self._create_fallback_individual_messages(chat, tool_results, ai_response)
```

#### C. Mixed Content Database Model
```python
# chat/models.py
class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=[("user", "User"), ("assistant", "Assistant")])
    content = models.TextField(blank=True)
    
    type = models.CharField(
        max_length=20,
        default="text",
        choices=[
            ("text", "Text"),
            ("quiz", "Quiz"),
            ("diagram", "Diagram"),
            ("youtube", "YouTube"),
            ("flashcard_update", "Flashcard Update"),
            ("background_process", "Background Process"),
            ("mixed", "Mixed Content"),  # For multiple tools
        ],
    )
    
    # Structured data fields
    structured_content = models.JSONField(null=True, blank=True)  # YouTube videos
    mixed_content_data = models.JSONField(null=True, blank=True)  # Mixed content structure
    quiz_html = models.TextField(blank=True, null=True)
    diagram_image = models.ForeignKey(DiagramImage, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Content type flags
    has_diagram = models.BooleanField(default=False)
    has_youtube = models.BooleanField(default=False)
    has_quiz = models.BooleanField(default=False)
    has_code = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    def is_mixed_content(self):
        """Check if this message contains mixed content types"""
        return (
            self.type == "mixed" or 
            sum([self.has_diagram, self.has_youtube, self.has_quiz, self.has_code]) > 1
        )
```

---

## 🔧 Key Supporting Services

### A. AI Models Service
```python
# chat/ai_models.py
class AIService:
    """Handles AI model integrations"""
    
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.default_model = "llama3-8b-8192"
    
    async def get_completion(self, messages: List[Dict], model: str = None) -> str:
        """Get a single completion from AI model"""
        try:
            completion = await sync_to_async(self.groq_client.chat.completions.create)(
                model=model or self.default_model,
                messages=messages,
                max_tokens=4000,
                temperature=0.7,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"AI completion error: {e}")
            return "I'm sorry, I encountered an error processing your request."
    
    async def stream_completion(self, messages: List[Dict], model: str = None):
        """Get streaming completion from AI model"""
        try:
            stream = await sync_to_async(self.groq_client.chat.completions.create)(
                model=model or self.default_model,
                messages=messages,
                max_tokens=4000,
                temperature=0.7,
                stream=True,
            )
            return stream
        except Exception as e:
            logger.error(f"AI streaming error: {e}")
            return None
```

### B. Chat Service
```python
# chat/services.py
class ChatService:
    """Main service layer coordinating AI interactions"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.groq_client = Groq()
    
    async def stream_completion(self, messages, query=None, files_rag=None, max_tokens=4000, chat_id=None, attached_file_name=None):
        """Stream AI completion with optional RAG context"""
        
        if files_rag and query:
            # RAG-enhanced completion
            relevant_docs = files_rag.retrieve_docs(query, chat_id)
            
            if relevant_docs:
                # Build context from retrieved documents
                context = "\n\n".join([doc.page_content for doc in relevant_docs])
                enhanced_messages = messages.copy()
                enhanced_messages.append({
                    "role": "system",
                    "content": f"Use this context to answer the user's question:\n\n{context}"
                })
                messages = enhanced_messages
        
        # Stream response
        stream = await sync_to_async(self.groq_client.chat.completions.create)(
            model="llama3-8b-8192",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )
        
        return stream
    
    async def generate_diagram_image(self, chat_history_messages, user_query, chat_id, user_id):
        """Generate diagram using AI + Graphviz"""
        # Implementation for diagram generation
        pass
    
    async def generate_quiz_from_query(self, chat_history_messages, user_query, chat_id, user_id):
        """Generate interactive quiz from conversation context"""
        # Implementation for quiz generation
        pass
    
    async def get_youtube_agent_response(self, user_message, chat_history):
        """Get YouTube recommendations or video summaries"""
        from .agent_tools import run_youtube_agent
        return await sync_to_async(run_youtube_agent)(user_message, chat_history)
    
    def get_chat_history(self, chat, limit=20):
        """Get recent chat history for context"""
        messages = chat.messages.all().order_by('-created_at')[:limit]
        return list(reversed(messages))
    
    def update_chat_title(self, chat, user_message):
        """Generate and update chat title based on first message"""
        if len(user_message) <= 50:
            chat.title = user_message
        else:
            # Generate title using AI
            chat.title = user_message[:47] + "..."
        chat.save()
```

### C. Database Models Summary
```python
# chat/models.py - Key models for features

class Chat(models.Model):
    """Main chat container"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="chats")
    title = models.CharField(max_length=100, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    """Individual messages with support for multiple content types"""
    # [Full implementation shown in Mixed Content section above]

class DiagramImage(models.Model):
    """Generated diagram storage"""
    # [Implementation shown in Diagram Generation section]

class ChatRAGFile(models.Model):
    """Uploaded documents for RAG"""
    # [Implementation shown in RAG System section]

class DocumentChunk(models.Model):
    """Vector-indexed document chunks"""
    # [Implementation shown in RAG System section]

class ChatFlashcard(models.Model):
    """Generated flashcards"""
    # [Implementation shown in Flashcard System section]

class ChatQuestionBank(models.Model):
    """Quiz questions bank"""
    # [Implementation shown in Quiz Generation section]
```

---

## 🎯 Summary

This comprehensive feature tracing guide covers all major post-login features in MentorAI:

1. **Chat Message Processing** - Core conversation handling with agent system coordination
2. **Diagram Generation** - Visual content creation using AI + Graphviz
3. **YouTube Integration** - Video recommendations and summarization
4. **Quiz Generation** - Interactive assessment creation and question banking
5. **Flashcard System** - Study card generation using Gemini AI
6. **RAG Document System** - Context-aware conversations with uploaded documents
7. **Study Hub** - Centralized study materials management
8. **Chat Management** - CRUD operations for conversations
9. **User Preferences** - Personalized learning experience adaptation
10. **Mixed Content Handling** - Coordinated multi-tool responses

Each feature includes the complete implementation chain from user interaction through database storage, with actual class names, function names, and code examples from your MentorAI codebase.
