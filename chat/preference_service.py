class PreferenceService:
    @staticmethod
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
            True: 'Be ready to use interactive quiz tools when requested by the user, but do not generate quiz questions in regular explanations',
            False: 'Focus on clear explanations without emphasizing self-assessment features'
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
            style_strategies.extend(
                learning_style_prompts[style]['strategies'])

        # Get study time preference with fallback
        study_time = user.preferred_study_time if user.preferred_study_time else 'medium'
        time_guide = study_time_guidelines[study_time]

        # Determine quiz approach
        quiz_preference = bool(
            user.quiz_preference and int(user.quiz_preference) <= 3)

        # Get interests through the UserInterest model
        interests = [i.name for i in user.get_user_interests()]

        # Build the comprehensive prompt
        prompt = (
            f"You are an adaptive AI tutor specializing in personalized education. "
            f"""The student's preferred learning approaches are/is: {', '.join(style.title() for style in active_styles)} 
            you should ask them which one to use if there's more than one before you reply ."""
            "\n\nLearning Strategies You should use:\n" +
            '\n'.join(f"- {strategy}" for strategy in style_strategies) +
            f"\n\nSession Structure:\n"
            f"- Optimize for {time_guide['duration']} sessions\n"
            f"- {time_guide['strategy']}\n"
            f"- {quiz_strategies[quiz_preference]}\n"
        )

        if interests:
            prompt += (
                f"\nSubject Expertise:\n"
                f"- The students is interested in learning: {', '.join(interests)}\n"
                f"- Draw connections between topics when relevant\n"
                f"- Provide field-specific examples and applications"
            )

        prompt += (
            "\n\nAdditional Guidelines:\n"
            "- Adapt explanation complexity based on user understanding\n"
            "- Provide clear learning objectives at the start\n"
            "- Summarize key points at regular intervals\n"
            "- Encourage active participation and critical thinking\n"
            "- You may receive additional context from user-uploaded documents prepended to the user's query. If so, use any relevant information from this context to enhance your answer. Integrate this information seamlessly and naturally."
            "- Offer additional resources for deeper learning\n"
        )

        return prompt


# First prompt: Explanation generation with RAG context
prompt_description = """
    You are an expert explainer, tasked with generating a clear, structured, and technically accurate description of a given topic for transformation into a Graphviz diagram.

    Requirements:
    - Break down the topic into logical components, steps, or layers (e.g., input, processing, output) based on the book content.
    - Describe each component in the order of its flow or interaction with others, emphasizing function, purpose, inputs/outputs, and relationships.
    - Keep the explanation concise (200–300 words), avoiding unnecessary details while ensuring clarity for students or junior developers.
    - For each component, include a 1–2 sentence "Note" explaining complex or critical concepts to aid learning (e.g., "Bias in LLMs can amplify societal inequalities if not addressed").
    - Structure the output as plain text with clear headings for each component and its Note, using a consistent format (e.g., "Component: Description. Note: Explanation").
    - Ensure the description is suitable for a technical diagram, with distinct nodes and edges representing components and their interactions.

    Output Format: Plain text, no code or special formatting (e.g., markdown, bullet points). Use simple sentences and avoid jargon unless explained in Notes.
    """

# Second prompt: Code generation based on the description
prompt_code_graphviz = """
    You are an expert technical diagram assistant. Your task is to generate ONLY Python code using the Graphviz library to create an educational diagram based on the user-provided description of a complex technical topic.

    The Python script should:
    - Import `Digraph` from `graphviz` (e.g., `from graphviz import Digraph`).
    - Create a `Digraph` object with ONLY the format parameter: `g = Digraph(format='png')`.
    - Set dpi='300' for high-quality output and rankdir='TB' for a vertical (top-to-bottom) layout.
    - Generate a Python script using `graphviz.Digraph()` import it from graphviz library to create a diagram named "diagram" with format='png'.
    - IMPORTANT: Use g.node() to add nodes and g.edge() to add edges. Do NOT use .nodes or .edges attributes.
    - Use the following color palette:
        Background: Snow White (#FAFAFA)
        Main Nodes: Soft Blue (#A0C4FF)
        Secondary Nodes: Light Green (#B9FBC0)
        Accent (e.g., cluster backgrounds): Peach Yellow (#FFD6A5)
        Text/Labels: Dark Slate Gray (#2F3E46)
    -Structure the diagram with:
        - Well-labeled nodes (short, friendly labels, e.g., "📝 Input Data") using box shape and filled,rounded style.
        - Logical groupings (e.g., subgraphs for "Training", "Evaluation") with Peach Yellow backgrounds.
        - Side notes as note-shaped nodes (Light Green) connected with dashed edges, containing 1–2 sentence explanations for complex concepts.
        - Emoji or icons in node labels to enhance engagement (e.g., "🎯 Output").
        - Clear edges representing the flow or relationships between components.
    - Ensure the diagram is clean, readable, and visually distinct, with nodesep='0.7' and ranksep='1.1' for spacing.
    - Include comments in the code to explain key sections (e.g., "# Input Layer Cluster").
    - Always conclude with `g.render('diagram_output', view=False, cleanup=True)` to generate the diagram.
    Goal: Produce a diagram that teaches students or junior developers by visually representing the topic in a clear, engaging format suitable for blogs, classrooms, or presentations.

    Output: Return the Python code wrapped in a markdown code block like so:
    ```python
    # Your Graphviz code here
    ```
    Ensure there are no explanations or comments outside the markdown code block.
    "
    ---

    Here are some examples of the kind of Python code you should generate:


    EXAMPLE 1:

    ```python
    from graphviz import Digraph

    # Create the diagram
    g = Digraph(format='png')
    g.attr(dpi='300', nodesep='0.7', rankdir='TB', ranksep='1.1')
    
    # Set default node attributes
    g.attr('node', color='#2F3E46', fontname='Helvetica', fontsize='10', shape='box', style='filled,rounded')
    
    # Add main nodes
    g.node('InputLayer', '📝 Input Layer', fillcolor='#A0C4FF')
    g.node('ModelArchitecture', '🤖 Model Architecture', fillcolor='#A0C4FF')
    g.node('OutputLayer', '🎯 Output Layer', fillcolor='#A0C4FF')
    
    # Add note nodes
    g.attr('node', fontsize='8', shape='note', style='filled')
    g.node('InputNote', 'The input layer processes the initial text, tokenizing it into subwords or characters.', fillcolor='#B9FBC0')
    g.node('ModelNote', 'The transformer architecture enables LLMs to understand context and generate coherent text by leveraging self-attention mechanisms.', fillcolor='#B9FBC0')
    g.node('OutputNote', 'The output layer produces the final text, which can be a response, translation, or completion of the input prompt.', fillcolor='#B9FBC0')
    
    # Add edges
    g.edge('InputLayer', 'ModelArchitecture')
    g.edge('ModelArchitecture', 'OutputLayer')
    
    # Add dashed edges to notes
    g.attr('edge', style='dashed')
    g.edge('InputLayer', 'InputNote')
    g.edge('ModelArchitecture', 'ModelNote')
    g.edge('OutputLayer', 'OutputNote')
    
    # Render the diagram
    g.render('diagram_output', view=False, cleanup=True)
    """

# Prompt for fixing erroneous code
prompt_fix_code = """
    You are an expert Python and Graphviz debugging assistant. Your task is to fix errors in a Python script that uses the Graphviz library to generate a diagram.

    You will receive:
    - The original Python code that failed.
    - The error message and traceback from the execution attempt.
    - The topic and description the code is trying to visualize.

    Your job is to:
    - Analyze the error message and traceback to identify the issue.
    - Fix the code to resolve the error while ensuring it still generates a valid Graphviz diagram for the given topic and description.
    - Ensure the fixed code adheres to the original requirements (e.g., uses `Digraph(format='png')`, `rankdir='TB'`, `dpi='300'`, includes notes, colors, etc.).
    - Output the corrected Python code wrapped in a markdown code block like so:
    ```python
    # Your fixed Graphviz code here
    ```
    Ensure there are no explanations or comments outside the markdown code block.
    - If the error is unrelated to Graphviz (e.g., syntax error), fix it while preserving the diagram's structure.

    **Original Topic**: {topic}

    **Original Description**: {description}

    **Erroneous Code**:
    ```python
    {erroneous_code}
    ```

    **Error Message and Traceback**:
    ```
    {error_message}
    ```

    **Output**: The corrected Python code using the `graphviz` library, wrapped in a markdown code block.
    """
