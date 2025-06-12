class MultiStepRegistration {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 2;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initializeForm();
    }

    setupEventListeners() {
        // Next button
        document.getElementById('next-step').addEventListener('click', (e) => {
            e.preventDefault();
            this.nextStep();
        });

        // Previous button
        document.getElementById('prev-step').addEventListener('click', (e) => {
            e.preventDefault();
            this.prevStep();
        });

        // Profile image preview
        document.getElementById('profile_image').addEventListener('change', (e) => {
            this.previewImage(e);
        });

        // Learning style toggles
        document.querySelectorAll('.learning-style-toggle input[type="checkbox"]').forEach((checkbox) => {
            checkbox.addEventListener('change', (e) => {
                this.toggleLearningStyle(e.target);
            });
        });

        // Study time buttons
        document.querySelectorAll('.study-time-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectStudyTime(e.target);
            });
        });

        // Quiz preference radio buttons
        document.querySelectorAll('input[name="quiz_preference"]').forEach((radio) => {
            radio.addEventListener('change', (e) => {
                this.updateQuizPreference(e.target);
            });
        });

        // Interest management
        this.initializeInterests();

        // Form submission
        document.querySelector('form').addEventListener('submit', (e) => {
            this.handleSubmit(e);
        });

        // Intercept Enter key on first step to go to next step instead of submit
        document.querySelector('form').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // Only intercept if not on textarea or file input
                const tag = e.target.tagName.toLowerCase();
                if (tag === 'textarea' || tag === 'button' || tag === 'select' || e.target.type === 'file') return;
                if (this.currentStep === 1) {
                    e.preventDefault();
                    this.nextStep();
                }
                // On last step, allow submit
            }
            // Intercept Tab on last input of step 1
            if (e.key === 'Tab' && !e.shiftKey && this.currentStep === 1) {
                const lastInput = document.getElementById('password2');
                if (e.target === lastInput) {
                    e.preventDefault();
                    this.nextStep();
                    // Optionally, focus the first input of step 2 after transition
                    setTimeout(() => {
                        const firstStep2 = document.querySelector('#step-2 input, #step-2 select, #step-2 button');
                        if (firstStep2) firstStep2.focus();
                    }, 650); // match slide transition
                }
            }
        });
    }

    initializeForm() {
        this.updateStepIndicator();
        this.updateStepContent();
    }

    nextStep() {
        if (this.validateCurrentStep()) {
            if (this.currentStep < this.totalSteps) {
                this.currentStep++;
                this.slideToStep();
            }
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.slideToStep();
        }
    }

    slideToStep() {
        const container = document.querySelector('.steps-container');
        const formContainer = document.querySelector('.form-container');
        
        if (container && formContainer) {
            // Calculate the exact width of one step
            const stepWidth = formContainer.offsetWidth;
            const translateX = -((this.currentStep - 1) * stepWidth);
            container.style.transform = `translateX(${translateX}px)`;
        }
        
        this.updateStepIndicator();
        this.updateStepContent();
        
        // Scroll to top smoothly
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    updateStepIndicator() {
        document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
            const stepNumber = index + 1;
            if (stepNumber < this.currentStep) {
                // Completed step
                indicator.classList.remove('active', 'bg-blue-600', 'text-white', 'shadow-blue-500/40');
                indicator.classList.add('completed', 'bg-green-600', 'text-white', 'shadow-green-500/30', 'scale-105');
            } else if (stepNumber === this.currentStep) {
                // Active step
                indicator.classList.remove('completed', 'bg-green-600', 'shadow-green-500/30');
                indicator.classList.add('active', 'bg-blue-600', 'text-white', 'shadow-blue-500/40', 'scale-110');
            } else {
                // Inactive step
                indicator.classList.remove('active', 'completed', 'bg-blue-600', 'bg-green-600', 'text-white', 'shadow-blue-500/40', 'shadow-green-500/30', 'scale-105', 'scale-110');
            }
        });
        
        // Update progress line
        const progressLine = document.querySelector('.progress-line');
        if (progressLine) {
            progressLine.classList.remove('step-1', 'step-2');
            progressLine.classList.add(`step-${this.currentStep}`);
        }
    }

    updateStepContent() {
        // Update navigation buttons
        const prevBtn = document.getElementById('prev-step');
        const nextBtn = document.getElementById('next-step');
        const submitBtn = document.getElementById('submit-btn');

        if (this.currentStep === 1) {
            prevBtn.style.display = 'none';
            nextBtn.style.display = 'block';
            submitBtn.style.display = 'none';
        } else if (this.currentStep === this.totalSteps) {
            prevBtn.style.display = 'block';
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'block';
        } else {
            prevBtn.style.display = 'block';
            nextBtn.style.display = 'block';
            submitBtn.style.display = 'none';
        }
    }

    validateCurrentStep() {
        if (this.currentStep === 1) {
            return this.validateBasicInfo();
        } else if (this.currentStep === 2) {
            return this.validatePreferences();
        }
        return true;
    }

    validateBasicInfo() {
        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const password1 = document.getElementById('password1').value;
        const password2 = document.getElementById('password2').value;

        if (!username) {
            this.showError('Username is required');
            return false;
        }
        if (!email) {
            this.showError('Email is required');
            return false;
        }
        if (!password1) {
            this.showError('Password is required');
            return false;
        }
        if (password1 !== password2) {
            this.showError('Passwords do not match');
            return false;
        }
        return true;
    }

    validatePreferences() {
        const learningStyles = ['visual', 'auditory', 'kinesthetic', 'reading'];
        const hasStyle = learningStyles.some(style => 
            document.querySelector(`input[name="learning_style_${style}"]`).checked
        );

        if (!hasStyle) {
            this.showError('Please select at least one learning style');
            return false;
        }

        const studyTime = document.getElementById('preferred_study_time').value;
        if (!studyTime) {
            this.showError('Please select a preferred study session length');
            return false;
        }

        return true;
    }

    showError(message) {
        // Remove existing error messages
        const existingError = document.querySelector('.step-error');
        if (existingError) {
            existingError.remove();
        }

        // Create and show new error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'step-error p-4 mb-4 text-red-200 bg-red-800 rounded-lg';
        errorDiv.textContent = message;

        const currentStepElement = document.querySelector(`#step-${this.currentStep}`);
        currentStepElement.insertBefore(errorDiv, currentStepElement.firstChild);

        // Remove error after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }

    previewImage(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.createElement('img');
                preview.src = e.target.result;
                preview.classList.add('w-full', 'h-32', 'object-cover', 'rounded-lg');
                const container = document.querySelector('label[for="profile_image"]');
                container.innerHTML = '';
                container.appendChild(preview);
            };
            reader.readAsDataURL(file);
        }
    }

    toggleLearningStyle(checkbox) {
        const label = checkbox.nextElementSibling;
        if (checkbox.checked) {
            // Selected state - gradient background with enhanced styling
            label.classList.remove('border-gray-600', 'bg-gray-700/50');
            label.classList.add('bg-gradient-to-br', 'from-blue-600', 'to-blue-700', 'border-blue-500', 'shadow-lg', 'shadow-blue-500/25', '-translate-y-0.5');
        } else {
            // Unselected state
            label.classList.remove('bg-gradient-to-br', 'from-blue-600', 'to-blue-700', 'border-blue-500', 'shadow-lg', 'shadow-blue-500/25', '-translate-y-0.5');
            label.classList.add('border-gray-600', 'bg-gray-700/50');
        }
    }

    selectStudyTime(btn) {
        // Reset all buttons to unselected state
        document.querySelectorAll('.study-time-btn').forEach(b => {
            b.classList.remove('bg-gradient-to-br', 'from-blue-600', 'to-blue-700', 'border-blue-500', 'shadow-lg', 'shadow-blue-500/25', '-translate-y-0.5');
            b.classList.add('border-gray-600', 'bg-gray-700/50');
        });
        
        // Set selected button to selected state
        btn.classList.remove('border-gray-600', 'bg-gray-700/50');
        btn.classList.add('bg-gradient-to-br', 'from-blue-600', 'to-blue-700', 'border-blue-500', 'shadow-lg', 'shadow-blue-500/25', '-translate-y-0.5');
        
        document.getElementById('preferred_study_time').value = btn.dataset.value;
    }

    updateQuizPreference(radio) {
        // Hide all labels first
        document.querySelectorAll('[data-rating]').forEach(label => {
            label.classList.add('opacity-0');
        });

        // Show clicked label and edge labels
        document.querySelector(`[data-rating="${radio.value}"]`).classList.remove('opacity-0');
        document.querySelector('[data-rating="1"]').classList.remove('opacity-0');
        document.querySelector('[data-rating="5"]').classList.remove('opacity-0');

        // Update text based on selection
        const ratingTexts = {
            1: 'Very helpful',
            2: 'Helpful',
            3: 'Neutral',
            4: 'Not very helpful',
            5: 'Not helpful'
        };

        document.querySelector(`[data-rating="${radio.value}"]`).textContent = ratingTexts[radio.value];
    }

    initializeInterests() {
        const interestInput = document.getElementById('interest-input');
        const suggestionsDiv = document.getElementById('interest-suggestions');
        const selectedInterests = document.getElementById('selected-interests');

        const predefinedInterests = [
            { id: 1, name: 'Machine Learning' },
            { id: 2, name: 'Deep Learning' },
            { id: 3, name: 'Natural Language Processing' },
            { id: 4, name: 'Computer Vision' },
            { id: 5, name: 'Artificial Intelligence' },
            { id: 6, name: 'Data Science' },
            { id: 7, name: 'Python Programming' },
            { id: 8, name: 'Data Structures & Algorithms' },
            { id: 9, name: 'Databases' },
            { id: 10, name: 'Web Development' },
            { id: 11, name: 'Cloud Computing' },
            { id: 12, name: 'Cybersecurity' },
            { id: 13, name: 'Robotics' },
            { id: 14, name: 'Data Engineering' }
        ];

        const createInterestTag = (name, id = null) => {
            const tag = document.createElement('div');
            tag.className = 'interest-tag px-3 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-sm text-white rounded-full flex items-center gap-2 transition-all duration-300 hover:scale-105 hover:shadow-lg hover:shadow-blue-500/25 cursor-pointer';
            tag.innerHTML = `
                <span>${name}</span>
                <button type="button" class="remove-interest text-white hover:text-red-300 transition-colors duration-200 font-bold text-lg leading-none">×</button>
                <input type="hidden" name="interests" value="${name}">
            `;
            tag.querySelector('.remove-interest').addEventListener('click', () => {
                tag.remove();
                showSuggestions(interestInput.value);
            });
            return tag;
        };

        const showSuggestions = (input) => {
            const value = input.toLowerCase();
            const selectedValues = Array.from(selectedInterests.querySelectorAll('.interest-tag'))
                .map(tag => tag.querySelector('span').textContent.toLowerCase());

            const filtered = predefinedInterests.filter(interest =>
                interest.name.toLowerCase().includes(value) &&
                !selectedValues.includes(interest.name.toLowerCase())
            );

            if (filtered.length && value) {
                suggestionsDiv.innerHTML = filtered.map(interest => `
                    <div class="suggestion p-2 hover:bg-gray-600 cursor-pointer" data-id="${interest.id}">
                        ${interest.name}
                    </div>
                `).join('');
                suggestionsDiv.classList.remove('hidden');
            } else {
                suggestionsDiv.classList.add('hidden');
            }
        };

        interestInput.addEventListener('input', () => {
            showSuggestions(interestInput.value);
        });

        interestInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && interestInput.value.trim()) {
                e.preventDefault();
                const interest = interestInput.value.trim();
                const selectedValues = Array.from(selectedInterests.querySelectorAll('.interest-tag'))
                    .map(tag => tag.querySelector('span').textContent.toLowerCase());

                if (!selectedValues.includes(interest.toLowerCase())) {
                    selectedInterests.appendChild(createInterestTag(interest));
                }
                interestInput.value = '';
                suggestionsDiv.classList.add('hidden');
            }
        });

        suggestionsDiv.addEventListener('click', (e) => {
            const suggestion = e.target.closest('.suggestion');
            if (suggestion) {
                selectedInterests.appendChild(createInterestTag(
                    suggestion.textContent.trim(),
                    suggestion.dataset.id
                ));
                interestInput.value = '';
                suggestionsDiv.classList.add('hidden');
            }
        });

        document.addEventListener('click', (e) => {
            if (!interestInput.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                suggestionsDiv.classList.add('hidden');
            }
        });
    }

    handleSubmit(e) {
        if (!this.validateCurrentStep()) {
            e.preventDefault();
            return false;
        }
        // Let the form submit naturally if validation passes
    }
}

// Initialize the multi-step registration when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MultiStepRegistration();
}); 