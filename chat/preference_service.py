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
            "- Offer additional resources for deeper learning"
        )

        return prompt