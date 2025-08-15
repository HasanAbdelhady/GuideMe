# 🎓 MentorAI - Intelligent Learning Assistant

[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-316192?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org/)
[![Railway](https://img.shields.io/badge/Deployed%20on-Railway-0B0D0E?style=flat&logo=railway&logoColor=white)](https://railway.app/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**MentorAI** is an advanced AI-powered learning assistant that provides personalized educational support through interactive conversations, intelligent tools, and adaptive learning features. Built with Django and powered by multiple AI models, it offers a comprehensive learning experience tailored to individual user preferences.

## 🌐 Live Demo

- **Production URL**: [https://guideme-eg.duckdns.org](https://guideme-eg.duckdns.org)

## ✨ Key Features

### 🤖 AI-Powered Chat System

- **Multi-Model AI Integration**: Supports Groq, Google Gemini, and other leading AI models
- **Intelligent Agent System**: Automatically selects and coordinates appropriate tools based on user queries
- **Streaming Responses**: Real-time response generation for better user experience
- **Context-Aware Conversations**: Maintains conversation history and context for coherent interactions

### 🛠️ Smart Learning Tools

#### 📊 Diagram Generation

- **Automatic Diagram Creation**: Generates flowcharts, mind maps, and technical diagrams using Graphviz
- **Context-Aware Visualization**: Creates relevant diagrams based on conversation content
- **Multiple Diagram Types**: Supports various diagram formats for different learning needs

#### 🎥 YouTube Integration

- **Video Summarization**: Extracts and summarizes content from YouTube videos
- **Audio Processing**: Converts video content to text for analysis
- **Learning Material Integration**: Incorporates video content into learning sessions

#### 📝 Quiz & Assessment System

- **Dynamic Quiz Generation**: Creates personalized quizzes based on learning content
- **Multiple Question Types**: Supports various question formats and difficulty levels
- **Progress Tracking**: Monitors learning progress and identifies knowledge gaps

#### 🗃️ Flashcard System

- **AI-Generated Flashcards**: Creates study cards from conversation content
- **Spaced Repetition**: Implements scientifically-backed learning algorithms
- **Personalized Study Sets**: Adapts to individual learning patterns

#### 🔍 RAG (Retrieval-Augmented Generation)

- **Document Processing**: Supports PDF and text document uploads
- **Vector Search**: Uses pgvector for semantic document search
- **Contextual Answers**: Provides answers based on uploaded learning materials

### 👤 User Management & Personalization

#### 🔐 Authentication System

- **Multiple Login Methods**:
  - Traditional username/email + password
  - Google OAuth integration
  - GitHub OAuth integration (configured)
- **Secure Backend**: Custom authentication backend supporting email or username login
- **Session Management**: Secure session handling with JWT token support

#### 🎯 Learning Preferences

- **Learning Style Assessment**: Visual, auditory, kinesthetic, and reading/writing preferences
- **Study Habit Tracking**: Personalized study time preferences and habits
- **Interest Management**: Subject-specific interest tracking and recommendations
- **Adaptive Interface**: UI adapts to user preferences and learning styles

### 💾 Data Management

- **Chat History**: Persistent conversation storage with UUID-based identification
- **Vector Database**: Advanced semantic search capabilities using PostgreSQL + pgvector
- **Media Storage**: Efficient handling of diagrams, images, and uploaded documents
- **User Profiles**: Comprehensive user preference and progress tracking

## 🏗️ Technical Architecture

### Backend Stack

- **Framework**: Django 5.2 with Django REST Framework
- **Database**: PostgreSQL 13+ with pgvector extension for vector operations
- **AI Integration**:
  - Groq API for fast inference
  - Google Generative AI (Gemini) for advanced reasoning
  - LangChain for AI workflow orchestration
- **Authentication**: Django Allauth with social authentication
- **File Processing**:
  - PDF processing with pdfminer.six
  - Image processing with Pillow
  - Video processing with yt-dlp

### Frontend Technologies

- **Styling**: Tailwind CSS for responsive design
- **JavaScript**: Vanilla JS with modern ES6+ features
- **Real-time Features**: WebSocket-like streaming for live responses
- **Responsive Design**: Mobile-first approach with dark mode support

### AI & ML Components

- **Agent System**: Intelligent tool selection and coordination
- **Vector Search**: Semantic similarity search using embeddings
- **Document Processing**: Advanced text extraction and chunking
- **Diagram Generation**: Automated visualization using Graphviz

## 🚀 Deployment Architecture

### Production Deployment

- **Platform**: Railway.app
- **Domain**: Custom DNS via DuckDNS (guideme-eg.duckdns.org)
- **SSL/TLS**: Automatic HTTPS certificate provisioning
- **Database**: Railway-managed PostgreSQL with pgvector
- **Static Files**: WhiteNoise for efficient static file serving
- **Process Management**: Gunicorn with multiple workers

### DNS Configuration

```
Type: A Record
Name: guideme-eg.duckdns.org
Value: 66.33.22.82 (Railway IP)
SSL: Automatic via Railway
```

### Environment Variables

```bash
# Core Django Settings
DEBUG=False
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=guideme-eg.duckdns.org,*.railway.app

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# AI API Keys
GROQ_API_KEY=your-groq-key
GOOGLE_API_KEY=your-google-key
FLASHCARD=your-gemini-key

# OAuth Credentials
GOOGLE_CLIENT_ID=your-google-oauth-id
GOOGLE_CLIENT_SECRET=your-google-oauth-secret
GITHUB_CLIENT_ID=your-github-oauth-id
GITHUB_CLIENT_SECRET=your-github-oauth-secret
```

## 🔧 Local Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 13+ with pgvector extension
- Node.js (for Tailwind CSS, optional)

### Installation Steps

1. **Clone the Repository**

```bash
git clone https://github.com/HasanAbdelhady/MentorAI.git
cd MentorAI
```

2. **Create Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**

```bash
pip install -r requirements.txt
```

4. **Database Setup**

```bash
# Install PostgreSQL and create database
createdb mentorai_dev

# Install pgvector extension
psql mentorai_dev -c "CREATE EXTENSION vector;"
```

5. **Environment Configuration**

```bash
# Create .env file
cp .env.example .env
# Edit .env with your configuration
```

6. **Database Migration**

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

7. **Create Superuser**

```bash
python manage.py createsuperuser
```

8. **Run Development Server**

```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

### Docker Development

```bash
# Build and run with Docker Compose
docker-compose up --build

# For production-like environment
docker-compose -f docker-compose.prod.yml up --build
```

## 📁 Project Structure

```
MentorAI/
├── chat/                          # Main chat application
│   ├── agent_system.py           # AI agent coordination
│   ├── ai_models.py              # AI service integration
│   ├── models.py                 # Database models
│   ├── views.py                  # API endpoints and views
│   ├── services.py               # Business logic services
│   ├── rag.py                    # RAG implementation
│   ├── tools/                    # AI tools directory
│   │   ├── base.py              # Base tool interface
│   │   ├── diagram_tool.py      # Diagram generation
│   │   ├── youtube_tool.py      # YouTube integration
│   │   ├── quiz_tool.py         # Quiz generation
│   │   ├── flashcard_tool.py    # Flashcard creation
│   │   └── context_tool.py      # Context management
│   ├── templates/chat/          # HTML templates
│   └── static/chat/             # CSS, JS, images
├── users/                        # User management
│   ├── models.py                # User and preference models
│   ├── views.py                 # Authentication views
│   ├── backends.py              # Custom auth backends
│   ├── adapters.py              # Social auth adapters
│   └── templates/users/         # User-related templates
├── chatgpt/                     # Main project settings
│   ├── settings.py              # Django configuration
│   ├── urls.py                  # URL routing
│   └── wsgi.py                  # WSGI application
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── docker-compose.yml          # Development Docker setup
├── docker-compose.prod.yml     # Production Docker setup
└── manage.py                   # Django management script
```

## 🔌 API Endpoints

### Chat Endpoints

- `GET /chat/` - Chat interface
- `POST /chat/message/` - Send message
- `GET /chat/history/<chat_id>/` - Get chat history
- `POST /chat/upload/` - Upload documents

### User Endpoints

- `POST /users/register/` - User registration
- `POST /users/login/` - User login
- `GET /users/profile/` - User profile
- `POST /users/token/` - JWT token generation

### Tool Endpoints

- `POST /chat/generate-quiz/` - Generate quiz
- `GET /chat/flashcards/` - Get flashcards
- `GET /chat/diagram/<id>/` - Get diagram image

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test chat
python manage.py test users

# Run with coverage
coverage run manage.py test
coverage report
```

## 🚀 Performance Features

- **Streaming Responses**: Real-time AI response delivery
- **Efficient Caching**: Redis-like caching for frequent queries
- **Vector Search**: Fast semantic search using pgvector
- **Async Processing**: Background task processing for heavy operations
- **CDN Integration**: Static file delivery optimization

## 🔒 Security Features

- **CSRF Protection**: Cross-site request forgery prevention
- **HTTPS Enforcement**: SSL/TLS encryption for all traffic
- **Secure Headers**: Security-focused HTTP headers
- **Input Sanitization**: XSS and injection attack prevention
- **Rate Limiting**: API abuse prevention
- **OAuth Security**: Secure third-party authentication

## 📊 Monitoring & Analytics

- **Error Tracking**: Comprehensive error logging
- **Performance Monitoring**: Response time tracking
- **User Analytics**: Learning progress tracking
- **System Metrics**: Database and server monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Hasan Abdelhady**

- GitHub: [@HasanAbdelhady](https://github.com/HasanAbdelhady)
- LinkedIn: [Hasan Abdelhady](https://linkedin.com/in/hasan-abdelhady)

## 🙏 Acknowledgments

- **OpenAI & Groq** for AI model access
- **Google** for Gemini AI integration
- **Railway** for seamless deployment platform
- **Django Community** for the excellent web framework
- **PostgreSQL Team** for the robust database system

## 📞 Support

For support, email support@mentorai.com or create an issue on GitHub.

---

**Made with ❤️ for learners worldwide**
