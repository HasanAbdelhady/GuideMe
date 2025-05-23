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
        quiz_preference = bool(user.quiz_preference and int(user.quiz_preference) <= 3)

        # Get interests through the UserInterest model
        interests = [i.name for i in user.get_user_interests()]

        # Build the comprehensive prompt
        prompt = (
            f"You are an adaptive AI tutor specializing in personalized education. "
            f"""The student's preferred learning approaches are/i: {', '.join(style.title() for style in active_styles)} 
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
            "- You may receive additional context from user-uploaded documents prepended to the user's query. If so, use any relevant information from this context to enhance your answer. Integrate this information seamlessly and naturally. CRITICALLY: DO NOT mention the context, its source, or your process of using it unless the user explicitly asks about how you obtained certain information.\n"
            "- Offer additional resources for deeper learning"
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
prompt_code_graphviz ="""
    You are an expert technical diagram assistant. Your task is to generate ONLY Python code using the Graphviz library to create an educational diagram based on the user-provided description of a complex technical topic.

    The Python script should:
    - Import `Digraph` from `graphviz` (e.g., `from graphviz import Digraph`).
    - Create a `Digraph` object with ONLY the format parameter: `g = Digraph(format='png')`.
    - Set dpi='300' for high-quality output and rankdir='TB' for a vertical (top-to-bottom) layout.
    - Generate a Python script using `graphviz.Digraph()` import it from graphviz library to create a diagram named "diagram" with format='png'.
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

    g = Digraph('Transformer', format='png')
    g.attr(rankdir='TB', dpi='300', nodesep='0.7', ranksep='1.1')
    g.attr('node', shape='box', style='filled,rounded', fontsize='10', fontname='Helvetica', color='#444444')

    # === Color Palette ===
    colors = {
        'attention': '#E6CCFF',     # lavender
        'masked_attention': '#FFD6CC',  # light peach
        'ff': '#D9F0FF',            # light blue
        'norm': '#E2F7E1',          # mint green
        'embed': '#FFE9EC',         # soft pink
        'pos': '#FFFFFF',           # white
        'final': '#FFFACD',         # lemon chiffon
        'label': '#F0F0F0'
    }

    # === Helper to make styled nodes ===
    def styled_node(name, label, fill):
        g.node(name, label, fillcolor=fill)

    # === ENCODER BLOCK ===
    styled_node('Input', '🡒 Inputs', 'white')
    styled_node('InputEmbed', 'Input Embedding', colors['embed'])
    styled_node('PosEnc1', 'Positional Encoding', colors['pos'])
    styled_node('EncMHA', 'Multi-Head Attention', colors['attention'])
    styled_node('EncNorm1', 'Add & Norm', colors['norm'])
    styled_node('EncFF', 'Feed Forward', colors['ff'])
    styled_node('EncNorm2', 'Add & Norm', colors['norm'])
    styled_node('EncoderNx', 'Nx Encoder Blocks', colors['label'])

    # === DECODER BLOCK ===
    styled_node('Output', '🡒 Outputs (shifted right)', 'white')
    styled_node('OutputEmbed', 'Output Embedding', colors['embed'])
    styled_node('PosEnc2', 'Positional Encoding', colors['pos'])
    styled_node('DecMaskedMHA', 'Masked MHA', colors['masked_attention'])
    styled_node('DecNorm1', 'Add & Norm', colors['norm'])
    styled_node('DecMHA', 'Multi-Head Attention\n(from Encoder)', colors['attention'])
    styled_node('DecNorm2', 'Add & Norm', colors['norm'])
    styled_node('DecFF', 'Feed Forward', colors['ff'])
    styled_node('DecNorm3', 'Add & Norm', colors['norm'])
    styled_node('DecoderNx', 'Nx Decoder Blocks', colors['label'])

    # === FINAL LAYERS ===
    styled_node('Linear', 'Linear', colors['final'])
    styled_node('Softmax', 'Softmax', colors['final'])
    styled_node('OutputProbs', '🎯 Output Probabilities', 'white')

    # === FLOW: Encoder ===
    g.edge('Input', 'InputEmbed')
    g.edge('InputEmbed', 'PosEnc1')
    g.edge('PosEnc1', 'EncMHA')
    g.edge('EncMHA', 'EncNorm1')
    g.edge('EncNorm1', 'EncFF')
    g.edge('EncFF', 'EncNorm2')
    g.edge('EncNorm2', 'EncoderNx')

    # === FLOW: Decoder ===
    g.edge('Output', 'OutputEmbed')
    g.edge('OutputEmbed', 'PosEnc2')
    g.edge('PosEnc2', 'DecMaskedMHA')
    g.edge('DecMaskedMHA', 'DecNorm1')
    g.edge('DecNorm1', 'DecMHA')
    g.edge('EncoderNx', 'DecMHA')  # Cross attention from encoder
    g.edge('DecMHA', 'DecNorm2')
    g.edge('DecNorm2', 'DecFF')
    g.edge('DecFF', 'DecNorm3')
    g.edge('DecNorm3', 'DecoderNx')

    # === FINAL FLOW ===
    g.edge('DecoderNx', 'Linear')
    g.edge('Linear', 'Softmax')
    g.edge('Softmax', 'OutputProbs')

    # === GROUP LABELS ===
    with g.subgraph() as encoder:
        encoder.attr(rank='same')
        encoder.node('EncoderNx')
        encoder.attr(label='<<B>ENCODER</B>>', labelloc='t', style='dashed')

    with g.subgraph() as decoder:
        decoder.attr(rank='same')
        decoder.node('DecoderNx')
        decoder.attr(label='<<B>DECODER</B>>', labelloc='t', style='dashed')

    # === Render ===
    g.render('diagram_output', view=True)
    ```
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

