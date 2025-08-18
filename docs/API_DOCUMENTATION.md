# 🔌 API Documentation

This document provides comprehensive API documentation for the MentorAI application, including all endpoints, request/response formats, and authentication requirements.

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Chat Endpoints](#chat-endpoints)
3. [User Management Endpoints](#user-management-endpoints)
4. [Tool-Specific Endpoints](#tool-specific-endpoints)
5. [File Management Endpoints](#file-management-endpoints)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)

## 🔐 Authentication

### Authentication Methods

MentorAI supports multiple authentication methods:

1. **Session-based Authentication** (Primary)
2. **JWT Token Authentication** (API access)
3. **OAuth 2.0** (Google, GitHub)

### Session Authentication

Most web interface interactions use Django's built-in session authentication:

```http
POST /users/login/
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secretpassword
```

**Response:**
```http
HTTP/1.1 302 Found
Location: /chat/
Set-Cookie: sessionid=abc123...; HttpOnly; Path=/
```

### JWT Token Authentication

For API access, obtain JWT tokens:

```http
POST /users/token/
Content-Type: application/json

{
    "username": "user@example.com",
    "password": "secretpassword"
}
```

**Response:**
```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Usage:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## 💬 Chat Endpoints

### Create New Chat

Creates a new chat session with an initial message.

```http
POST /chat/create/
Content-Type: application/x-www-form-urlencoded
Authorization: Session or Bearer token

prompt=Hello, I want to learn about machine learning
```

**Response:**
```json
{
    "success": true,
    "chat_id": "123e4567-e89b-12d3-a456-426614174000",
    "redirect_url": "/chat/123e4567-e89b-12d3-a456-426614174000/",
    "title": "Hello, I want to learn about..."
}
```

### Get Chat Interface

Renders the chat interface for a specific chat.

```http
GET /chat/{chat_id}/
Authorization: Session required
```

**Response:** HTML page with chat interface

**AJAX Request for Messages:**
```http
GET /chat/{chat_id}/
X-Requested-With: XMLHttpRequest
Authorization: Session required
```

**AJAX Response:**
```json
{
    "messages": [
        {
            "role": "user",
            "content": "Hello, I want to learn about machine learning"
        },
        {
            "role": "assistant",
            "content": "I'd be happy to help you learn about machine learning!"
        }
    ]
}
```

### Stream Chat Messages

Sends a message and receives streaming responses via Server-Sent Events.

```http
POST /chat/{chat_id}/stream/
Content-Type: multipart/form-data
Authorization: Session required

prompt=Explain neural networks
rag_mode_active=false
diagram_mode_active=false
youtube_mode_active=false
```

**Optional Form Fields:**
- `file`: File upload for document analysis
- `image_file`: Image upload for vision model analysis
- `rag_mode_active`: Enable RAG mode ("true"/"false")
- `diagram_mode_active`: Force diagram generation ("true"/"false")
- `youtube_mode_active`: Force YouTube mode ("true"/"false")
- `is_reprompt_after_edit`: Indicates message edit ("true"/"false")

**Response:** Server-Sent Events stream

```
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"type": "content", "content": "Neural networks are..."}

data: {"type": "diagram_image", "diagram_image_id": "uuid", "text_content": "Here's a diagram"}

data: {"type": "youtube_recommendations", "data": [{"title": "Neural Networks Explained", "url": "..."}]}

data: {"type": "quiz_html", "quiz_html": "<div class='quiz-question'>..."}

data: {"type": "done"}
```

### Chat Management

#### Update Chat Title
```http
POST /chat/{chat_id}/update-title/
Content-Type: application/json
Authorization: Session required

{
    "title": "New Chat Title"
}
```

#### Delete Chat
```http
POST /chat/{chat_id}/delete/
Authorization: Session required
```

#### Clear Chat Messages
```http
POST /chat/{chat_id}/clear/
Authorization: Session required
```

### Message Management

#### Edit Message
```http
POST /chat/{chat_id}/message/{message_id}/edit/
Content-Type: application/json
Authorization: Session required

{
    "new_content": "Updated message content"
}
```

**Response:**
```json
{
    "success": true,
    "edited_message_id": 123,
    "new_content": "Updated message content",
    "is_edited": true,
    "edited_at": "2024-01-15T10:30:00Z"
}
```

## 👤 User Management Endpoints

### User Registration

```http
POST /users/register/
Content-Type: multipart/form-data

username=johndoe
email=john@example.com
password1=securepassword123
password2=securepassword123
profile_image=@profile.jpg
learning_style_visual=1
learning_style_auditory=0
learning_style_kinesthetic=1
learning_style_reading=1
preferred_study_time=medium
quiz_preference=4
interests[]=Machine Learning
interests[]=Web Development
custom_interests=Additional interests here
```

**Response:** Redirects to `/chat/new/` with success message

### User Login

```http
POST /users/login/
Content-Type: application/x-www-form-urlencoded

username=john@example.com
password=securepassword123
```

### Google OAuth Registration Preferences

For users who signed up via Google OAuth:

```http
POST /users/register-preferences/
Content-Type: application/x-www-form-urlencoded
Authorization: Session required

learning_style_visual=1
learning_style_auditory=0
learning_style_kinesthetic=1
learning_style_reading=1
preferred_study_time=medium
quiz_preference=4
interests[]=Machine Learning
interests[]=Data Science
```

### User Profile Management

#### Get Profile
```http
GET /users/profile/
Authorization: Session required
```

#### Update Profile
```http
POST /users/profile/
Content-Type: multipart/form-data
Authorization: Session required

action=update_profile
email=newemail@example.com
profile_image=@newprofile.jpg
learning_style_visual=1
preferred_study_time=long
quiz_preference=5
```

#### Add Interest
```http
POST /users/profile/
Content-Type: application/x-www-form-urlencoded
Authorization: Session required

action=add_interest
interest_name=Deep Learning
```

#### Remove Interest
```http
POST /users/profile/
Content-Type: application/x-www-form-urlencoded
Authorization: Session required

action=remove_interest
interest_id=123
```

#### Change Password
```http
POST /users/profile/
Content-Type: application/x-www-form-urlencoded
Authorization: Session required

action=change_password
old_password=currentpassword
new_password1=newpassword123
new_password2=newpassword123
```

## 🛠️ Tool-Specific Endpoints

### Generate Quiz

Creates a quiz based on chat conversation history.

```http
POST /chat/{chat_id}/quiz/
Authorization: Session required
```

**Response:**
```json
{
    "quiz_html": "<div class='quiz-container'>...</div>",
    "message_id": 456
}
```

### Get Quiz HTML

Retrieves quiz HTML for a specific message.

```http
GET /chat/quiz_html/{message_id}/
Authorization: Session required
```

**Response:**
```json
{
    "quiz_html": "<div class='quiz-container'>...</div>",
    "message_id": 456,
    "content": "Here is your quiz:"
}
```

### Generate Flashcards

Standalone flashcard generation endpoint.

```http
POST /chat/flashcards/
Content-Type: application/json

{
    "topic": "Machine Learning Basics"
}
```

**Response:**
```json
{
    "flashcards": [
        {
            "term": "Neural Network",
            "definition": "A computing system inspired by biological neural networks"
        },
        {
            "term": "Gradient Descent",
            "definition": "An optimization algorithm used to minimize cost functions"
        }
    ]
}
```

### Serve Diagram Image

Retrieves a generated diagram image.

```http
GET /chat/diagram_image/{diagram_id}/
Authorization: Session required
```

**Response:**
```
Content-Type: image/png
Content-Length: 12345

[PNG image data]
```

### Study Hub

Access saved flashcards and quiz questions for a chat.

```http
GET /chat/{chat_id}/study/
Authorization: Session required
```

**Response:** HTML page with flashcards and question bank

## 📁 File Management Endpoints

### RAG File Management

#### List RAG Files
```http
GET /chat/{chat_id}/rag-files/
Authorization: Session required
```

**Response:**
```json
[
    {
        "id": "789",
        "name": "machine_learning_textbook.pdf"
    },
    {
        "id": "790",
        "name": "neural_networks_notes.txt"
    }
]
```

#### Upload RAG File
```http
POST /chat/{chat_id}/rag-files/
Content-Type: multipart/form-data
Authorization: Session required

file=@document.pdf
```

**Response:**
```json
{
    "success": true,
    "file": {
        "id": "791",
        "name": "document.pdf"
    }
}
```

#### Delete RAG File
```http
DELETE /chat/{chat_id}/rag-files/{file_id}/delete/
Authorization: Session required
```

**Response:**
```json
{
    "success": true,
    "message": "File removed from RAG context successfully."
}
```

## ⚠️ Error Handling

### Standard Error Response Format

```json
{
    "error": "Error message description",
    "details": "Additional error details (optional)",
    "status": "error"
}
```

### Common HTTP Status Codes

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| `400` | Bad Request | Invalid input, missing required fields |
| `401` | Unauthorized | Missing or invalid authentication |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Resource doesn't exist or user lacks access |
| `413` | Payload Too Large | File upload exceeds size limit |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server-side error, API failures |

### Error Examples

#### Authentication Required
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
    "error": "Authentication required"
}
```

#### Chat Not Found
```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
    "error": "Chat not found"
}
```

#### File Upload Error
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "error": "Invalid file type. Only PDF and TXT are allowed."
}
```

#### API Rate Limit
```http
HTTP/1.1 413 Payload Too Large
Content-Type: application/json

{
    "error": "The request is too large for the model. Please try reducing your message size or shortening the conversation if the history is very long."
}
```

## 🚦 Rate Limiting

### External API Limits

The application implements intelligent rate limiting for external API calls:

1. **Groq API**: Respects API rate limits with exponential backoff
2. **Google Gemini**: Rate limiting for flashcard generation
3. **YouTube API**: Quota management for video searches
4. **HuggingFace API**: Embedding generation rate limiting

### File Upload Limits

- **Maximum file size**: 10MB per file
- **Maximum files per chat**: 10 files
- **Supported formats**: PDF, TXT for RAG; Images for vision model

### Chat Limits

- **Maximum message length**: ~8000 characters
- **Maximum chat history context**: Last 20 messages for LLM
- **Concurrent requests**: Limited per user session

## 📊 Response Types

### Server-Sent Events (SSE) Types

When streaming chat responses, different event types are sent:

| Type | Description | Data Structure |
|------|-------------|----------------|
| `content` | Text content chunks | `{"type": "content", "content": "text"}` |
| `diagram_image` | Diagram generated | `{"type": "diagram_image", "diagram_image_id": "uuid", "text_content": "description"}` |
| `youtube_recommendations` | Video recommendations | `{"type": "youtube_recommendations", "data": [video_objects]}` |
| `quiz_html` | Interactive quiz | `{"type": "quiz_html", "quiz_html": "<div>..."}` |
| `mixed_content_start` | Multiple tools used | `{"type": "mixed_content_start"}` |
| `notification` | Background process result | `{"type": "notification", "content": "message"}` |
| `file_info` | File processing status | `{"type": "file_info", "status": "truncated", "message": "warning"}` |
| `metadata` | Additional information | `{"type": "metadata", "content": {stats}}` |
| `error` | Error occurred | `{"type": "error", "content": "error message"}` |
| `done` | Stream complete | `{"type": "done"}` |

### Mixed Content Structure

When multiple tools are used simultaneously:

```json
{
    "type": "mixed",
    "components": [
        {
            "type": "diagram",
            "content": "Diagram description",
            "order": 0,
            "diagram_image_id": "uuid"
        },
        {
            "type": "youtube",
            "content": "Video recommendations",
            "order": 1,
            "videos": [...]
        },
        {
            "type": "quiz",
            "content": "Quiz description",
            "order": 2,
            "quiz_html": "<div>..."
        }
    ],
    "ai_response": "Brief contextual message"
}
```

This API documentation provides a comprehensive guide for integrating with and understanding the MentorAI application's endpoints and data structures.
