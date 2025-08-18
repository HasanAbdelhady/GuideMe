# 📊 Diagram Tool Documentation

The DiagramTool is responsible for generating visual diagrams to help explain complex concepts, processes, and relationships in response to user queries.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Activation Logic](#activation-logic)
3. [Diagram Generation Process](#diagram-generation-process)
4. [Supported Diagram Types](#supported-diagram-types)
5. [Integration with Agent System](#integration-with-agent-system)
6. [Error Handling](#error-handling)
7. [Examples](#examples)

## 🎯 Overview

The DiagramTool automatically creates visual representations when users request diagrams or when complex topics would benefit from visualization. It uses Graphviz to generate professional-quality diagrams from AI-generated DOT language code.

### Key Features

- **Automatic Trigger Detection**: Recognizes when users want visual explanations
- **Context-Aware Generation**: Creates diagrams based on conversation history
- **Multiple Diagram Types**: Supports flowcharts, architectures, processes, and more
- **High-Quality Output**: Uses Graphviz for professional diagram rendering
- **Database Storage**: Diagrams are stored and served efficiently

### Technical Stack

- **AI Model**: Groq API for DOT code generation
- **Rendering Engine**: Graphviz (dot command)
- **Storage**: PostgreSQL with binary data storage
- **Serving**: Custom Django view for image delivery

## 🎯 Activation Logic

### Confidence Scoring Algorithm

```mermaid
graph TD
    A[User Message] --> B[Convert to Lowercase]
    B --> C[Check High Confidence Patterns]
    C --> D{Pattern Match?}
    D -->|Yes| E[Return 0.9 Confidence]
    D -->|No| F[Check Trigger Keywords]
    F --> G{Keyword Found?}
    G -->|Yes| H[Return 0.6 Confidence]
    G -->|No| I[Check Context Clues]
    I --> J{Complex Explanation?}
    J -->|Yes| K[Return 0.3 Confidence]
    J -->|No| L[Return 0.0 Confidence]
```

### High Confidence Patterns (0.9)

```python
high_confidence_patterns = [
    r"(create|make|generate|draw|show)\s+(a\s+)?(diagram|chart|flowchart)",
    r"visualize",
    r"show me (how|the process|the flow|the architecture)",
    r"explain (visually|with a diagram)",
]
```

**Examples that trigger high confidence:**
- "Create a diagram showing the process"
- "Can you visualize this for me?"
- "Show me how this works"
- "Draw a flowchart of the algorithm"
- "Explain this visually"

### Medium Confidence Keywords (0.6)

```python
triggers = [
    "diagram", "chart", "visualize", "draw", "flowchart",
    "architecture", "process flow", "explain visually", "visual representation"
]
```

**Examples that trigger medium confidence:**
- "I need a flowchart"
- "What's the architecture like?"
- "Can you draw this?"

### Low Confidence Context (0.3)

For messages longer than 10 words containing process-related terms:
- "process", "workflow", "architecture", "system"

**Examples that trigger low confidence:**
- "Explain the entire software development process from start to finish"
- "How does the authentication system architecture work in detail?"

## 🔄 Diagram Generation Process

### End-to-End Flow

```mermaid
sequenceDiagram
    participant User
    participant DiagramTool
    participant ChatService
    participant AI as Groq API
    participant Graphviz
    participant Database
    participant Frontend
    
    User->>DiagramTool: Request with high confidence
    DiagramTool->>ChatService: generate_diagram_image()
    ChatService->>AI: Generate DOT code prompt
    AI-->>ChatService: Return DOT language code
    ChatService->>ChatService: Validate and clean DOT code
    ChatService->>Graphviz: Render diagram (dot command)
    Graphviz-->>ChatService: Return PNG image bytes
    ChatService->>Database: Save DiagramImage record
    Database-->>ChatService: Return diagram_id
    ChatService-->>DiagramTool: Return diagram_id
    DiagramTool-->>User: ToolResult with diagram_id
    Frontend->>Database: GET /chat/diagram_image/{id}/
    Database-->>Frontend: Serve PNG image
```

### Detailed Implementation

#### 1. Prompt Construction
```python
def build_diagram_prompt(chat_history, user_query):
    context = extract_relevant_context(chat_history)
    
    prompt = f"""Based on this conversation context and user query, generate a Graphviz DOT language diagram.

Context: {context}
User Query: {user_query}

Create a clear, well-structured diagram using DOT syntax. Include:
- Proper node and edge definitions
- Clear labels and relationships
- Appropriate layout (digraph, graph, etc.)
- Professional styling

Return only the DOT code, no explanations."""
    
    return prompt
```

#### 2. DOT Code Generation
The tool sends the constructed prompt to Groq API and receives DOT language code:

```dot
digraph user_registration {
    rankdir=TB;
    node [shape=box, style=filled, fillcolor=lightblue];
    
    start [label="User Visits Site", fillcolor=lightgreen];
    auth_check [label="Check Authentication", shape=diamond, fillcolor=yellow];
    register_form [label="Registration Form"];
    validation [label="Form Validation", shape=diamond, fillcolor=yellow];
    create_user [label="Create User Account"];
    setup_preferences [label="Setup Preferences"];
    redirect_chat [label="Redirect to Chat", fillcolor=lightcoral];
    
    start -> auth_check;
    auth_check -> register_form [label="Not Authenticated"];
    register_form -> validation;
    validation -> create_user [label="Valid"];
    validation -> register_form [label="Invalid"];
    create_user -> setup_preferences;
    setup_preferences -> redirect_chat;
}
```

#### 3. Image Rendering
```python
async def render_diagram(dot_code: str) -> bytes:
    """Render DOT code to PNG using Graphviz"""
    try:
        # Save DOT code to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
            f.write(dot_code)
            dot_file_path = f.name
        
        # Generate PNG using Graphviz
        png_file_path = dot_file_path.replace('.dot', '.png')
        subprocess.run([
            'dot', '-Tpng', dot_file_path, '-o', png_file_path
        ], check=True)
        
        # Read generated PNG
        with open(png_file_path, 'rb') as f:
            image_bytes = f.read()
        
        # Cleanup temporary files
        os.unlink(dot_file_path)
        os.unlink(png_file_path)
        
        return image_bytes
        
    except subprocess.CalledProcessError as e:
        raise DiagramGenerationError(f"Graphviz rendering failed: {e}")
```

#### 4. Database Storage
```python
# Create DiagramImage record
diagram_image = DiagramImage.objects.create(
    chat=chat,
    user=user,
    image_data=image_bytes,
    filename=f"diagram_{uuid.uuid4().hex[:8]}.png",
    content_type="image/png"
)

return diagram_image.id
```

## 📊 Supported Diagram Types

### 1. Flowcharts
**Use Case**: Process flows, decision trees, algorithms
```dot
digraph flowchart {
    rankdir=TB;
    start -> decision;
    decision -> action1 [label="yes"];
    decision -> action2 [label="no"];
}
```

### 2. System Architecture
**Use Case**: Software architecture, network diagrams
```dot
digraph architecture {
    subgraph cluster_frontend {
        label="Frontend Layer";
        ui [label="User Interface"];
    }
    
    subgraph cluster_backend {
        label="Backend Layer";
        api [label="API Server"];
        db [label="Database"];
    }
    
    ui -> api;
    api -> db;
}
```

### 3. Entity Relationships
**Use Case**: Database schemas, object relationships
```dot
graph er_diagram {
    User -- Chat [label="owns"];
    Chat -- Message [label="contains"];
    User -- Interest [label="has"];
}
```

### 4. Mind Maps
**Use Case**: Concept relationships, learning topics
```dot
graph mindmap {
    center [label="Machine Learning", shape=circle, fillcolor=gold];
    center -- supervised [label="Supervised Learning"];
    center -- unsupervised [label="Unsupervised Learning"];
    center -- reinforcement [label="Reinforcement Learning"];
}
```

### 5. Timeline Diagrams
**Use Case**: Project timelines, historical events
```dot
digraph timeline {
    rankdir=LR;
    node [shape=box];
    
    phase1 [label="Planning\n(Week 1-2)"];
    phase2 [label="Development\n(Week 3-8)"];
    phase3 [label="Testing\n(Week 9-10)"];
    phase4 [label="Deployment\n(Week 11)"];
    
    phase1 -> phase2 -> phase3 -> phase4;
}
```

## 🤝 Integration with Agent System

### Tool Registration
```python
class ChatAgentSystem:
    def __init__(self, chat_service, ai_service):
        self.tools = [
            DiagramTool(chat_service),  # Registered here
            # ... other tools
        ]
```

### Execution in Agent Context
```python
async def execute(self, user_message: str, chat_context: Dict[str, Any]) -> ToolResult:
    try:
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
        else:
            return ToolResult(success=False, error="Failed to generate diagram")
            
    except Exception as e:
        logger.error(f"DiagramTool error: {e}", exc_info=True)
        return ToolResult(success=False, error=f"Diagram generation error: {str(e)}")
```

### Frontend Integration
```javascript
// Handle diagram events from server-sent events
if (data.type === 'diagram_image') {
    const diagramId = data.diagram_image_id;
    const imageUrl = `/chat/diagram_image/${diagramId}/`;
    
    // Create image element
    const img = document.createElement('img');
    img.src = imageUrl;
    img.className = 'diagram-image max-w-full h-auto rounded-lg shadow-lg';
    img.alt = 'Generated diagram';
    
    // Add to chat interface
    messageContainer.appendChild(img);
}
```

## 🛡️ Error Handling

### Common Error Scenarios

#### 1. Invalid DOT Code
```python
def validate_dot_code(dot_code: str) -> bool:
    """Basic validation of DOT syntax"""
    if not dot_code.strip():
        return False
    
    # Check for basic DOT structure
    has_graph_declaration = bool(re.search(r'(di)?graph\s+\w+\s*{', dot_code))
    has_closing_brace = '}' in dot_code
    
    return has_graph_declaration and has_closing_brace
```

#### 2. Graphviz Rendering Errors
```python
try:
    subprocess.run(['dot', '-Tpng', dot_file, '-o', png_file], check=True)
except subprocess.CalledProcessError as e:
    logger.error(f"Graphviz rendering failed: {e}")
    # Fallback: Try with simpler layout engine
    subprocess.run(['neato', '-Tpng', dot_file, '-o', png_file], check=True)
```

#### 3. File System Errors
```python
def ensure_temp_directory():
    """Ensure temporary directory exists and is writable"""
    temp_dir = '/tmp/diagrams'
    os.makedirs(temp_dir, exist_ok=True)
    
    if not os.access(temp_dir, os.W_OK):
        raise PermissionError(f"Cannot write to {temp_dir}")
```

#### 4. Database Storage Errors
```python
try:
    diagram_image = DiagramImage.objects.create(...)
except IntegrityError as e:
    logger.error(f"Database constraint violation: {e}")
    return None
except Exception as e:
    logger.error(f"Unexpected database error: {e}")
    return None
```

### Error Recovery Strategies

1. **DOT Code Cleanup**: Remove problematic syntax elements
2. **Alternative Layout Engines**: Try different Graphviz engines (dot, neato, circo)
3. **Simplified Diagrams**: Generate basic diagrams if complex ones fail
4. **Graceful Degradation**: Return text description if diagram generation fails

## 📝 Examples

### Example 1: Process Flow Request

**User Input:**
> "Show me the user registration process flow"

**Generated DOT Code:**
```dot
digraph user_registration {
    rankdir=TB;
    node [shape=box, style=filled, fillcolor=lightblue];
    
    start [label="User Visits Site", fillcolor=lightgreen];
    check_auth [label="Check Authentication", shape=diamond, fillcolor=yellow];
    reg_form [label="Show Registration Form"];
    fill_form [label="User Fills Form"];
    validate [label="Validate Input", shape=diamond, fillcolor=yellow];
    create_user [label="Create User Account"];
    setup_prefs [label="Setup Preferences"];
    login [label="Auto Login"];
    redirect [label="Redirect to Chat", fillcolor=lightcoral];
    
    start -> check_auth;
    check_auth -> reg_form [label="Not Authenticated"];
    reg_form -> fill_form;
    fill_form -> validate;
    validate -> create_user [label="Valid"];
    validate -> reg_form [label="Invalid"];
    create_user -> setup_prefs;
    setup_prefs -> login;
    login -> redirect;
}
```

### Example 2: System Architecture Request

**User Input:**
> "Visualize the MentorAI system architecture"

**Generated DOT Code:**
```dot
digraph mentorai_architecture {
    rankdir=TB;
    
    subgraph cluster_frontend {
        label="Frontend Layer";
        style=filled;
        fillcolor=lightgray;
        
        ui [label="Web Interface"];
        js [label="JavaScript Client"];
    }
    
    subgraph cluster_application {
        label="Application Layer";
        style=filled;
        fillcolor=lightblue;
        
        django [label="Django Framework"];
        agent [label="Agent System"];
        tools [label="AI Tools"];
    }
    
    subgraph cluster_services {
        label="Service Layer";
        style=filled;
        fillcolor=lightyellow;
        
        chat_svc [label="Chat Service"];
        ai_svc [label="AI Service"];
        rag_svc [label="RAG Pipeline"];
    }
    
    subgraph cluster_data {
        label="Data Layer";
        style=filled;
        fillcolor=lightcoral;
        
        postgres [label="PostgreSQL"];
        files [label="File Storage"];
    }
    
    ui -> django;
    js -> django;
    django -> agent;
    agent -> tools;
    tools -> chat_svc;
    chat_svc -> ai_svc;
    tools -> rag_svc;
    django -> postgres;
    django -> files;
}
```

### Example 3: Learning Concept Map

**User Input:**
> "Create a diagram showing machine learning concepts"

**Generated DOT Code:**
```dot
graph ml_concepts {
    layout=neato;
    
    ml [label="Machine Learning", shape=circle, fillcolor=gold, style=filled, pos="0,0!"];
    
    supervised [label="Supervised\nLearning", pos="2,1!"];
    unsupervised [label="Unsupervised\nLearning", pos="2,-1!"];
    reinforcement [label="Reinforcement\nLearning", pos="0,-2!"];
    
    classification [label="Classification", pos="4,2!"];
    regression [label="Regression", pos="4,0!"];
    
    clustering [label="Clustering", pos="4,-1!"];
    dim_reduction [label="Dimensionality\nReduction", pos="4,-3!"];
    
    ml -- supervised;
    ml -- unsupervised;
    ml -- reinforcement;
    
    supervised -- classification;
    supervised -- regression;
    
    unsupervised -- clustering;
    unsupervised -- dim_reduction;
}
```

The DiagramTool provides a powerful way to enhance learning through visual representation, automatically detecting when diagrams would be helpful and generating appropriate visualizations based on the conversation context.
