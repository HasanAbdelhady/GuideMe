# chat/config.py
"""
Centralized configuration for the chat application.
This file contains all configurable constants to avoid repetition and make maintenance easier.
"""

import os
from typing import Any, Dict

# ============================================================================
# AI MODEL CONFIGURATION
# ============================================================================

# Primary LLM model for chat completions
DEFAULT_LLM_MODEL = "openai/gpt-oss-120b"

# Gemini model for specialized tasks (flashcards, diagrams, quizzes)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Model-specific configurations
MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "openai/gpt-oss-20b": {
        "temperature": 0.7,
        "max_tokens": 6500,
        "max_completion_tokens": 1024,
    },
    "llama3-8b-8192": {  # Legacy support
        "temperature": 0.7,
        "max_tokens": 6000,
        "max_completion_tokens": 1024,
    },
    "gemini-2.5-flash": {
        "temperature": 0.7,
        "max_tokens": 8192,
        "max_completion_tokens": 8192,
    },
}

# ============================================================================
# API CONFIGURATION
# ============================================================================

# API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
FLASHCARD_API_KEY = os.environ.get("FLASHCARD")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API")
HUGGINGFACE_API_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN")

# ============================================================================
# CHAT CONFIGURATION
# ============================================================================

# Token limits
HARD_MAX_TOKENS_API = 5800
SAFETY_BUFFER = 250
TOKEN_ESTIMATION_MULTIPLIER = 1.4

# File processing
MAX_RAG_FILES = 10
MAX_FILE_CHARS = 15000

# ============================================================================
# YOUTUBE CONFIGURATION
# ============================================================================

MAX_YOUTUBE_RESULTS = 10

# ============================================================================
# EMBEDDING CONFIGURATION
# ============================================================================

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_model_config(model_name: str = None) -> Dict[str, Any]:
    """Get configuration for a specific model."""
    model_name = model_name or DEFAULT_LLM_MODEL
    return MODEL_CONFIGS.get(model_name, MODEL_CONFIGS[DEFAULT_LLM_MODEL])


def get_default_model() -> str:
    """Get the default LLM model name."""
    return DEFAULT_LLM_MODEL


def get_gemini_model() -> str:
    """Get the default Gemini model name."""
    return DEFAULT_GEMINI_MODEL
