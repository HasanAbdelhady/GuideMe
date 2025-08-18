# 🏗️ System Architecture Documentation

This document provides a comprehensive overview of the MentorAI system architecture, including component interactions, data flow, and technical design decisions.

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Component Interactions](#component-interactions)
4. [Database Schema](#database-schema)
5. [AI/ML Pipeline](#aiml-pipeline)
6. [Security Architecture](#security-architecture)
7. [Deployment Architecture](#deployment-architecture)

## 🎯 System Overview

MentorAI is a Django-based intelligent learning assistant that combines traditional web application architecture with modern AI capabilities. The system uses an agent-based approach to coordinate multiple AI tools and provide personalized educational experiences.

### High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web Interface]
        JS[JavaScript Chat Client]
        CSS[Responsive UI Components]
    end
    
    subgraph "Application Layer"
        Django[Django Web Framework]
        Views[View Controllers]
        Agent[Agent System]
        Tools[AI Tools]
    end
    
    subgraph "Service Layer"
        ChatSvc[Chat Service]
        AISvc[AI Service]
        PrefSvc[Preference Service]
        RAGSvc[RAG Pipeline]
    end
    
    subgraph "Data Layer"
        PostgreSQL[(PostgreSQL + pgvector)]
        Redis[(Redis Cache)]
        FileStorage[File Storage]
    end
    
    subgraph "External Services"
        Groq[Groq API]
        Gemini[Google Gemini]
        HF[HuggingFace]
        YouTube[YouTube API]
    end
    
    UI --> Django
    JS --> Views
    Views --> Agent
    Agent --> Tools
    Tools --> ChatSvc
    ChatSvc --> AISvc
    AISvc --> Groq
    AISvc --> Gemini
    RAGSvc --> HF
    Tools --> RAGSvc
    Django --> PostgreSQL
    Django --> Redis
    Django --> FileStorage
    Tools --> YouTube
```

## 🏛️ Architecture Layers

### 1. Presentation Layer

**Technologies:** HTML5, CSS3 (Tailwind), Vanilla JavaScript, Server-Sent Events (SSE)

**Components:**
- `chat.html` - Main chat interface
- `chat.js` - Client-side chat logic
- `stream_handler.js` - Real-time message streaming
- Responsive design with mobile support

**Key Features:**
- Real-time streaming responses
- Dynamic content rendering (diagrams, quizzes, videos)
- File upload interface
- Interactive quiz components

### 2. Application Layer

**Framework:** Django 5.2+ with async support

**Core Components:**

#### Views & Controllers
```mermaid
graph TD
    A[ChatView] --> B[Renders chat interface]
    C[ChatStreamView] --> D[Handles message streaming]
    E[UserRegistrationView] --> F[User onboarding]
    G[ChatRAGFilesView] --> H[File management]
    
    D --> I[Agent System]
    I --> J[Tool Coordination]
    J --> K[AI Service Integration]
```

#### Agent System Architecture
```mermaid
graph TD
    A[ChatAgentSystem] --> B[Message Analysis]
    B --> C[Tool Selection Algorithm]
    C --> D[Parallel Tool Execution]
    D --> E[Result Aggregation]
    E --> F[Response Generation]
    
    subgraph "Available Tools"
        T1[DiagramTool]
        T2[YouTubeTool] 
        T3[QuizTool]
        T4[FlashcardTool]
    end
    
    C --> T1
    C --> T2
    C --> T3
    C --> T4
```

### 3. Service Layer

#### Chat Service (`ChatService`)
- Message processing and storage
- AI model integration
- Tool result coordination
- Context management

#### AI Service (`AIService`)
- Multi-model AI integration (Groq, Gemini)
- Response streaming
- Model selection logic
- Rate limiting and error handling

#### RAG Pipeline (`RAG_pipeline`)
- Document processing (PDF, TXT)
- Vector embedding generation
- Semantic search implementation
- PostgreSQL vector storage

#### Preference Service (`PreferenceService`)
- User preference management
- System prompt generation
- Learning style adaptation

### 4. Data Layer

#### PostgreSQL Database with pgvector Extension

**Key Features:**
- Vector similarity search for RAG
- ACID compliance for data integrity
- JSON field support for flexible schemas
- UUID primary keys for scalability

#### Redis Cache (Optional)
- Session storage
- Temporary data caching
- Rate limiting counters

## 🔄 Component Interactions

### Message Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant ChatStreamView
    participant AgentSystem
    participant Tools
    participant AIService
    participant Database
    
    User->>Frontend: Send message
    Frontend->>ChatStreamView: POST /chat/{id}/stream/
    ChatStreamView->>AgentSystem: process_message()
    
    AgentSystem->>Tools: Evaluate can_handle() for each tool
    Tools-->>AgentSystem: Return confidence scores
    AgentSystem->>Tools: Execute selected tools in parallel
    Tools->>AIService: Generate content (diagrams, quizzes, etc.)
    Tools-->>AgentSystem: Return ToolResult objects
    
    AgentSystem->>AIService: Generate contextual AI response
    AIService-->>AgentSystem: Return AI response (stream or text)
    AgentSystem-->>ChatStreamView: Return AI response + tool results
    
    ChatStreamView->>Database: Save messages
    ChatStreamView->>Frontend: Stream results via SSE
    Frontend->>User: Display response + tool outputs
```

### RAG Document Processing

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant RAGFilesView
    participant RAGPipeline
    participant HuggingFace
    participant PostgreSQL
    
    User->>Frontend: Upload document
    Frontend->>RAGFilesView: POST file
    RAGFilesView->>PostgreSQL: Save ChatRAGFile
    RAGFilesView->>PostgreSQL: Clear existing vector index
    
    Note over RAGPipeline: Next query triggers index rebuild
    
    User->>Frontend: Send query with RAG mode
    Frontend->>RAGPipeline: Process query
    RAGPipeline->>RAGPipeline: Extract text from documents
    RAGPipeline->>RAGPipeline: Split into chunks
    RAGPipeline->>HuggingFace: Generate embeddings
    RAGPipeline->>PostgreSQL: Store DocumentChunk with vectors
    RAGPipeline->>PostgreSQL: Vector similarity search
    PostgreSQL-->>RAGPipeline: Return relevant chunks
    RAGPipeline-->>Frontend: Stream response with context
```

## 🗄️ Database Schema

### Core Models

```mermaid
erDiagram
    CustomUser ||--o{ Chat : owns
    CustomUser ||--o{ UserInterest : has
    Interest ||--o{ UserInterest : referenced_by
    
    Chat ||--o{ Message : contains
    Chat ||--o{ ChatRAGFile : has
    Chat ||--o{ DiagramImage : contains
    Chat ||--o{ ChatFlashcard : has
    Chat ||--o{ ChatQuestionBank : has
    Chat ||--o{ DocumentChunk : indexed_from
    Chat ||--|| ChatVectorIndex : has
    
    ChatRAGFile ||--o{ DocumentChunk : chunked_into
    DiagramImage ||--o{ Message : referenced_by
    
    CustomUser {
        uuid id PK
        string username UK
        string email UK
        string password_hash
        boolean learning_style_visual
        boolean learning_style_auditory
        boolean learning_style_kinesthetic
        boolean learning_style_reading
        string preferred_study_time
        int quiz_preference
        datetime created_at
    }
    
    Chat {
        uuid id PK
        uuid user_id FK
        string title
        datetime created_at
        datetime updated_at
    }
    
    Message {
        int id PK
        uuid chat_id FK
        string role
        text content
        string type
        json structured_content
        json mixed_content_data
        text quiz_html
        uuid diagram_image_id FK
        boolean has_diagram
        boolean has_youtube
        boolean has_quiz
        boolean has_code
        datetime created_at
        boolean is_edited
        datetime edited_at
    }
    
    DocumentChunk {
        uuid id PK
        uuid chat_id FK
        uuid rag_file_id FK
        text content
        int chunk_index
        vector embedding
        json metadata
        datetime created_at
    }
```

### Key Relationships

1. **User → Chat (1:N)**: Users can have multiple chats
2. **Chat → Message (1:N)**: Each chat contains multiple messages
3. **User → Interest (N:N)**: Users can have multiple interests through UserInterest
4. **Chat → RAG Files (1:N)**: Each chat can have multiple uploaded documents
5. **RAG File → Document Chunks (1:N)**: Files are split into searchable chunks
6. **Chat → Vector Index (1:1)**: Each chat has one vector index for RAG

## 🤖 AI/ML Pipeline

### Multi-Model AI Integration

```mermaid
graph TD
    A[User Query] --> B[Agent System]
    B --> C{Tool Selection}
    
    C --> D[Diagram Generation]
    C --> E[Quiz Creation]
    C --> F[Flashcard Generation]
    C --> G[YouTube Processing]
    C --> H[General Chat]
    
    D --> I[Groq API - Code Generation]
    E --> J[Groq API - Quiz HTML]
    F --> K[Gemini API - Flashcards]
    G --> L[Groq API - Summarization]
    H --> M[Groq API - Conversation]
    
    I --> N[Graphviz Rendering]
    J --> O[HTML Quiz Component]
    K --> P[Flashcard Database]
    L --> Q[YouTube Data Processing]
    M --> R[Text Response]
    
    N --> S[Mixed Content Response]
    O --> S
    P --> S
    Q --> S
    R --> S
```

### RAG (Retrieval-Augmented Generation) Pipeline

```mermaid
graph TD
    A[Document Upload] --> B[Text Extraction]
    B --> C[Chunking Strategy]
    C --> D[Embedding Generation]
    D --> E[Vector Storage]
    
    F[User Query] --> G[Query Embedding]
    G --> H[Vector Similarity Search]
    H --> I[Retrieve Relevant Chunks]
    I --> J[Context Assembly]
    J --> K[Augmented Prompt]
    K --> L[AI Response Generation]
    
    subgraph "Storage Layer"
        E --> M[(PostgreSQL + pgvector)]
        H --> M
    end
    
    subgraph "Embedding Service"
        D --> N[HuggingFace API]
        G --> N
    end
```

### Tool Confidence Scoring Algorithm

Each tool implements a `can_handle()` method that returns a confidence score (0.0-1.0):

```python
# Example confidence calculation
def can_handle(self, user_message: str, chat_context: Dict[str, Any]) -> float:
    message_lower = user_message.lower()
    
    # High confidence patterns (0.9)
    if re.search(r"(create|make|generate)\s+(a\s+)?(diagram|chart)", message_lower):
        return 0.9
    
    # Medium confidence keywords (0.6)
    if any(trigger in message_lower for trigger in self.triggers):
        return 0.6
    
    # Context-based scoring (0.3)
    if self._has_relevant_context(chat_context):
        return 0.3
    
    return 0.0
```

## 🔒 Security Architecture

### Authentication & Authorization

```mermaid
graph TD
    A[User Request] --> B{Authenticated?}
    B -->|No| C[Login Required]
    B -->|Yes| D[Check Permissions]
    
    C --> E[Traditional Login]
    C --> F[Google OAuth]
    C --> G[GitHub OAuth]
    
    E --> H[CustomAuthBackend]
    F --> I[AllAuth Integration]
    G --> I
    
    H --> J[Session Creation]
    I --> J
    J --> K[JWT Token Generation]
    
    D --> L{Authorized?}
    L -->|Yes| M[Process Request]
    L -->|No| N[403 Forbidden]
```

### Data Security Measures

1. **Input Sanitization**: All user inputs are sanitized to prevent XSS/injection attacks
2. **CSRF Protection**: Django's built-in CSRF protection for all forms
3. **SQL Injection Prevention**: Django ORM parameterized queries
4. **File Upload Security**: Type validation and secure storage paths
5. **API Rate Limiting**: Protection against abuse of external APIs
6. **Secure Headers**: Security-focused HTTP headers implementation

### Privacy & Data Protection

- User chat data is isolated per user account
- RAG files are stored in user-specific directories
- Vector embeddings are associated with specific chats
- User preferences are encrypted in database
- Optional data retention policies

## 🚀 Deployment Architecture

### Production Environment

```mermaid
graph TD
    subgraph "Load Balancer"
        LB[Nginx/Railway Load Balancer]
    end
    
    subgraph "Application Servers"
        APP1[Django App Instance 1]
        APP2[Django App Instance 2]
    end
    
    subgraph "Database Layer"
        PG[(PostgreSQL Primary)]
        REPLICA[(PostgreSQL Replica)]
    end
    
    subgraph "External Services"
        GROQ[Groq API]
        GEMINI[Google Gemini]
        HF[HuggingFace API]
        YT[YouTube API]
    end
    
    subgraph "Storage"
        MEDIA[Media Files Storage]
        STATIC[Static Files CDN]
    end
    
    LB --> APP1
    LB --> APP2
    APP1 --> PG
    APP2 --> PG
    PG --> REPLICA
    APP1 --> GROQ
    APP1 --> GEMINI
    APP1 --> HF
    APP1 --> YT
    APP1 --> MEDIA
    LB --> STATIC
```

### Scalability Considerations

1. **Horizontal Scaling**: Multiple Django app instances behind load balancer
2. **Database Scaling**: Read replicas for query optimization
3. **Caching Strategy**: Redis for session and query caching
4. **CDN Integration**: Static file delivery optimization
5. **Async Processing**: Background tasks for heavy operations
6. **API Rate Limiting**: Intelligent request throttling

### Monitoring & Observability

```mermaid
graph TD
    A[Application Metrics] --> B[Performance Monitoring]
    C[Error Tracking] --> D[Alert System]
    E[User Analytics] --> F[Usage Insights]
    G[System Metrics] --> H[Infrastructure Monitoring]
    
    B --> I[Response Time Tracking]
    D --> J[Error Rate Monitoring]
    F --> K[Feature Usage Analysis]
    H --> L[Resource Utilization]
```

## 🔧 Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Frontend** | HTML5, CSS3 (Tailwind), Vanilla JavaScript, SSE |
| **Backend** | Django 5.2+, Python 3.11+, Async Support |
| **Database** | PostgreSQL 13+ with pgvector extension |
| **Caching** | Redis (optional) |
| **AI/ML** | Groq API, Google Gemini, HuggingFace Transformers |
| **File Processing** | PyPDF2, pdfminer, yt-dlp |
| **Visualization** | Graphviz, Matplotlib |
| **Authentication** | Django AllAuth, OAuth 2.0 |
| **Deployment** | Railway, Docker, Nginx |
| **Monitoring** | Django Logging, Error Tracking |

This architecture provides a robust, scalable foundation for the MentorAI learning assistant while maintaining flexibility for future enhancements and integrations.
