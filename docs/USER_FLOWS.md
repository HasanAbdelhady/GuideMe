# 🗺️ User Flows Documentation

This document outlines the key user journeys and interactions within the MentorAI application.

## 📋 Table of Contents

1. [Registration & Onboarding Flow](#registration--onboarding-flow)
2. [Chat Interaction Flow](#chat-interaction-flow)
3. [Tool Usage Flows](#tool-usage-flows)
4. [File Management Flow](#file-management-flow)
5. [Study Hub Flow](#study-hub-flow)

## 🚀 Registration & Onboarding Flow

### Traditional Registration

```mermaid
graph TD
    A[User visits site] --> B{Authenticated?}
    B -->|No| C[Registration Page]
    C --> D[CustomUserCreationForm]
    D --> E[Fill basic info: username, email, password]
    E --> F[Upload profile image - optional]
    F --> G[Learning Style Assessment]
    G --> H[Select Visual/Auditory/Kinesthetic/Reading preferences]
    H --> I[Choose Study Time Preference]
    I --> J[Set Quiz Preference Rating 1-5]
    J --> K[Select Interests from predefined list]
    K --> L[Add custom interests - optional]
    L --> M[Form Validation]
    M -->|Valid| N[Create CustomUser]
    M -->|Invalid| O[Show validation errors] --> D
    N --> P[Create UserInterest relationships]
    P --> Q[Auto-login user]
    Q --> R[Success message]
    R --> S[Redirect to New Chat]
    S --> T[ChatView with empty conversation]
```

### Google OAuth Registration

```mermaid
graph TD
    A[User clicks Google Sign-in] --> B[Google OAuth Flow]
    B --> C[User authorizes app]
    C --> D[Receive user data from Google]
    D --> E[Create/Update CustomUser]
    E --> F[Set session flag: google_signup=True]
    F --> G[Redirect to GoogleSignupPreferencesView]
    G --> H[Learning preferences form]
    H --> I[User fills preferences]
    I --> J[Save preferences to user model]
    J --> K[Create UserInterest relationships]
    K --> L[Clear session flags]
    L --> M[Welcome message]
    M --> N[Redirect to Chat]
```

### User Preference Collection Details

The system collects the following user preferences during registration:

**Learning Styles (Boolean flags):**
- `learning_style_visual`: Visual learning preference
- `learning_style_auditory`: Auditory learning preference  
- `learning_style_kinesthetic`: Hands-on learning preference
- `learning_style_reading`: Reading/writing learning preference

**Study Preferences:**
- `preferred_study_time`: "short", "medium", or "long" sessions
- `quiz_preference`: Integer 1-5 rating of quiz helpfulness

**Interests Management:**
- Predefined subject choices (ML, AI, Web Dev, etc.)
- Custom interests via text input
- Many-to-many relationship through `UserInterest` model

## 💬 Chat Interaction Flow

### New Chat Creation

```mermaid
graph TD
    A[User on chat interface] --> B[Types message in input field]
    B --> C[Clicks send or presses Enter]
    C --> D[POST to /chat/create/]
    D --> E[create_chat view processes request]
    E --> F[Create new Chat with message as title]
    F --> G[Create initial Message with role='user']
    G --> H[Return chat_id and redirect URL]
    H --> I[Frontend redirects to /chat/chat_id/]
    I --> J[ChatView.get renders chat interface]
    J --> K[User sees their message + empty assistant area]
```

### Message Processing Flow

```mermaid
graph TD
    A[User sends message] --> B[POST to /chat/chat_id/stream/]
    B --> C[ChatStreamView.post receives request]
    C --> D[Extract message, files, mode flags]
    D --> E[Get/create chat and validate user]
    E --> F[Process uploaded files if any]
    F --> G[Build messages_for_llm context]
    G --> H{RAG mode active?}
    H -->|Yes| I[Use RAG pipeline directly]
    H -->|No| J[Use Agent System]
    
    I --> K[files_rag_instance.retrieve_docs]
    K --> L[Generate response with document context]
    L --> M[Stream response to frontend]
    
    J --> N[agent_system.process_message]
    N --> O[Agent evaluates available tools]
    O --> P[Select and execute tools in parallel]
    P --> Q[Generate AI response based on tool results]
    Q --> R[Stream tool results + AI response]
    
    M --> S[Save messages to database]
    R --> S
    S --> T[Send 'done' signal to frontend]
```

### Agent System Decision Flow

```mermaid
graph TD
    A[Agent receives user message] --> B[Evaluate each tool's can_handle method]
    B --> C[DiagramTool.can_handle - checks for visualization keywords]
    B --> D[YouTubeTool.can_handle - checks for video/tutorial keywords]
    B --> E[QuizTool.can_handle - checks for quiz/test keywords]
    B --> F[FlashcardTool.can_handle - checks for study/flashcard keywords]
    
    C --> G{Confidence > 0.7?}
    D --> H{Confidence > 0.7?}
    E --> I{Confidence > 0.7?}
    F --> J{Confidence > 0.7?}
    
    G -->|Yes| K[Add DiagramTool to execution list]
    H -->|Yes| L[Add YouTubeTool to execution list]
    I -->|Yes| M[Add QuizTool to execution list]
    J -->|Yes| N[Add FlashcardTool to execution list]
    
    K --> O[Execute selected tools in parallel]
    L --> O
    M --> O
    N --> O
    
    O --> P[Collect ToolResult objects]
    P --> Q{Multiple tools used?}
    Q -->|Yes| R[Create mixed content message]
    Q -->|No| S[Create single tool message]
    R --> T[Generate contextual AI response]
    S --> T
    T --> U[Return AI response + tool results]
```

## 🛠️ Tool Usage Flows

### Diagram Generation Flow

```mermaid
graph TD
    A[User requests diagram] --> B[DiagramTool.can_handle evaluates message]
    B --> C[High confidence for keywords: diagram, visualize, flowchart]
    C --> D[DiagramTool.execute called]
    D --> E[chat_service.generate_diagram_image]
    E --> F[Build prompt from chat history + user query]
    F --> G[Send to AI model for Graphviz DOT code]
    G --> H[Parse and validate DOT code]
    H --> I[Generate image using Graphviz]
    I --> J[Save image to DiagramImage model]
    J --> K[Return diagram_image_id]
    K --> L[ToolResult with diagram data]
    L --> M[Frontend receives diagram_image event]
    M --> N[Load image via /chat/diagram_image/id/]
```

### YouTube Integration Flow

```mermaid
graph TD
    A[User mentions YouTube/videos] --> B[YouTubeTool.can_handle evaluates]
    B --> C{URL detected in message?}
    C -->|Yes| D[Video Summarization Path]
    C -->|No| E[Video Recommendation Path]
    
    D --> F[Extract YouTube URL]
    F --> G[Download audio using yt-dlp]
    G --> H[Transcribe audio to text]
    H --> I[Summarize with AI model]
    I --> J[Return text summary]
    
    E --> K[Extract topic from message]
    K --> L[Search YouTube API for educational videos]
    L --> M[Filter and rank results]
    M --> N[Return JSON list of video data]
    
    J --> O[ToolResult with text content]
    N --> P[ToolResult with structured video data]
    O --> Q[Frontend displays as text]
    P --> R[Frontend renders video recommendations]
```

### Quiz Generation Flow

```mermaid
graph TD
    A[User requests quiz] --> B[QuizTool.can_handle evaluates]
    B --> C[High confidence for: quiz, test, check understanding]
    C --> D[QuizTool.execute called]
    D --> E[chat_service.generate_quiz_from_query]
    E --> F[Build context from chat history]
    F --> G[Generate quiz HTML with AI model]
    G --> H[Parse and validate quiz HTML]
    H --> I[Extract individual questions]
    I --> J[Save questions to ChatQuestionBank]
    J --> K[Return quiz_html + content]
    K --> L[ToolResult with quiz data]
    L --> M[Frontend triggers quiz render]
    M --> N[Interactive quiz displayed to user]
```

### Flashcard Generation Flow

```mermaid
graph TD
    A[User requests flashcards] --> B[FlashcardTool.can_handle evaluates]
    B --> C[Detects study/flashcard keywords]
    C --> D[FlashcardTool.execute called]
    D --> E[Extract key concepts from chat history]
    E --> F[Generate flashcards with Gemini model]
    F --> G[Parse flashcard data]
    G --> H[Save to ChatFlashcard model]
    H --> I[Return flashcard data]
    I --> J[ToolResult with flashcard_update type]
    J --> K[Frontend shows flashcard notification]
    K --> L[User can access via Study Hub]
```

## 📁 File Management Flow

### RAG File Upload Flow

```mermaid
graph TD
    A[User clicks 'Manage RAG Context'] --> B[File upload modal opens]
    B --> C[User selects PDF/TXT file]
    C --> D[POST to /chat/chat_id/rag-files/]
    D --> E[ChatRAGFilesView.post processes upload]
    E --> F[Validate file type and size]
    F --> G[Check file limit per chat - 10 max]
    G --> H[Create ChatRAGFile instance]
    H --> I[Save file to media/rag_files/user_id/chat_id/]
    I --> J[Clear existing vector index]
    J --> K[Return success response]
    K --> L[Frontend updates file list]
    L --> M[Next RAG query triggers index rebuild]
```

### RAG Query Processing

```mermaid
graph TD
    A[User sends message with RAG mode active] --> B[Check for existing vector index]
    B --> C{Vector index exists?}
    C -->|No| D[Build new vector index]
    C -->|Yes| E[Use existing index]
    
    D --> F[Load all RAG files for chat]
    F --> G[Extract text from PDFs/TXT files]
    G --> H[Split into chunks with RecursiveCharacterTextSplitter]
    H --> I[Generate embeddings with HuggingFace model]
    I --> J[Store chunks + embeddings in DocumentChunk model]
    J --> K[Update ChatVectorIndex record]
    
    E --> L[Generate query embedding]
    K --> L
    L --> M[Perform cosine similarity search in PostgreSQL]
    M --> N[Retrieve top 4 most similar chunks]
    N --> O[Build context with retrieved documents]
    O --> P[Generate AI response with document context]
    P --> Q[Stream response to user]
```

## 📚 Study Hub Flow

### Study Hub Access

```mermaid
graph TD
    A[User clicks 'Study Hub' in chat] --> B[GET /chat/chat_id/study/]
    B --> C[study_hub_view processes request]
    C --> D[Get all ChatFlashcard objects for chat]
    D --> E[Get all ChatQuestionBank objects for chat]
    E --> F[Render study_hub.html template]
    F --> G[Display flashcards section]
    G --> H[Display question bank section]
    H --> I[User can review/practice with saved content]
```

### Flashcard Review Flow

```mermaid
graph TD
    A[User accesses Study Hub] --> B[View saved flashcards]
    B --> C[Click on flashcard to flip]
    C --> D[Show definition]
    D --> E[User self-assesses understanding]
    E --> F[Update confidence_level and review_count]
    F --> G[Spaced repetition algorithm determines next review]
    G --> H[Update last_reviewed timestamp]
```

## 🔄 Mixed Content Flow

When multiple tools are triggered simultaneously:

```mermaid
graph TD
    A[Agent detects multiple tools needed] --> B[Execute all tools in parallel]
    B --> C[Collect all ToolResult objects]
    C --> D[Create mixed_content_structure]
    D --> E[Set content type flags: has_diagram, has_youtube, etc.]
    E --> F[Generate brief contextual AI response]
    F --> G[Create Message with type='mixed']
    G --> H[Store mixed_content_data JSON]
    H --> I[Stream mixed_content_start event]
    I --> J[Stream each tool result in execution order]
    J --> K[Stream AI contextual response]
    K --> L[Frontend renders all components together]
```

## 🔍 Error Handling Flows

### Tool Execution Errors

```mermaid
graph TD
    A[Tool execution fails] --> B[Tool returns ToolResult with success=False]
    B --> C[Agent system logs error]
    C --> D[Continue with other tools if any]
    D --> E[Generate AI response explaining what went wrong]
    E --> F[User sees error message + partial results]
```

### Chat System Errors

```mermaid
graph TD
    A[Error in chat stream] --> B{Error type?}
    B -->|API Rate Limit| C[Show rate limit message]
    B -->|Network Error| D[Show retry option]
    B -->|Server Error| E[Show generic error message]
    C --> F[Stream error event to frontend]
    D --> F
    E --> F
    F --> G[Frontend displays user-friendly error]
    G --> H[User can retry or continue]
```

## 📊 Key User Actions Summary

| User Action | Endpoint | View/Function | Result |
|-------------|----------|---------------|---------|
| Register | `/users/register/` | `UserRegistrationView.post` | Creates user + preferences |
| Login | `/users/login/` | `LoginView` | Authenticates user |
| New Chat | `/chat/create/` | `create_chat` | Creates Chat + initial Message |
| Send Message | `/chat/{id}/stream/` | `ChatStreamView.post` | Streams AI response + tool results |
| Upload RAG File | `/chat/{id}/rag-files/` | `ChatRAGFilesView.post` | Saves file + clears vector index |
| Generate Quiz | Tool triggered by keywords | `QuizTool.execute` | Creates interactive quiz |
| Generate Diagram | Tool triggered by keywords | `DiagramTool.execute` | Creates visual diagram |
| Access Study Hub | `/chat/{id}/study/` | `study_hub_view` | Shows saved flashcards/questions |
| Edit Message | `/chat/{id}/message/{msg_id}/edit/` | `edit_message` | Updates message + deletes subsequent ones |

This documentation provides a comprehensive overview of how users interact with the MentorAI system, from initial registration through advanced features like RAG-enhanced conversations and AI tool coordination.
