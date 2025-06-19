import os
import datetime
import json
from .models import Message, DiagramImage
from users.models import CustomUser
from .preference_service import PreferenceService, prompt_description, prompt_code_graphviz, prompt_fix_code
from django.core.files.storage import default_storage
from io import StringIO
import logging
import copy
from functools import lru_cache
import time
# import base64 # No longer needed if generate_mindmap_image_data_url is removed
import asyncio
from asgiref.sync import sync_to_async
import traceback  # Added for error logging in retry logic
import sys
import locale
from typing import List, Dict, Any

# --- LangChain Imports ---
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts.example_selector import LengthBasedExampleSelector
from langchain.docstore.document import Document

# --- PDFMiner for PDF Loading ---
from pdfminer.high_level import extract_text

# --- Groq LangChain LLM Wrapper ---
from langchain.llms.base import LLM
from typing import Optional, List, Any
from groq import Groq
from pydantic import PrivateAttr

import graphviz  # Added for diagram generation
import re  # Added for sanitizing filenames
from .models import Chat
from django.conf import settings  # Added for MEDIA_ROOT
import google.generativeai as genai
from .agent_service import run_youtube_agent


def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\\\|?*]', '_', filename)


FLASHCARD_API_KEY = os.environ.get("FLASHCARD")

# Configure the generative AI model for flashcards
genai.configure(api_key=FLASHCARD_API_KEY)
flashcard_model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")


class GroqLangChainLLM(LLM):
    model: str = "llama3-8b-8192"
    _client: Any = PrivateAttr()

    def __init__(self, model="llama3-8b-8192", **kwargs):
        super().__init__(model=model, **kwargs)
        self._client = Groq()

    @property
    def _llm_type(self) -> str:
        return "groq"

    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
        messages = [{"role": "user", "content": prompt}]
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_completion_tokens=1024,
            stream=False,
            stop=stop,
        )
        return completion.choices[0].message.content


class LangChainRAG:
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2", model="llama3-8b-8192"):
        self.embedding_model_name = embedding_model_name
        self.vectorstore = None
        self.retriever = None
        self.qa_chain = None
        self.chunks = []
        self.model = model

    # Expects a list of tuples: [(file_path, file_type), ...]
    def build_index(self, file_paths_and_types):
        all_loaded_docs = []
        if not file_paths_and_types:
            # Handle case with no files gracefully, perhaps by not building any index or raising a specific error.
            # For now, if no files, vectorstore and retriever will remain None.
            # self.chunks will be empty.
            return

        for file_path, file_type in file_paths_and_types:
            docs_from_file = []
            if file_type == "pdf":
                try:
                    # Ensure file_path exists and is a file before passing to extract_text
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        self.logger.warning(
                            f"PDF file not found or is not a file: {file_path}. Skipping.")
                        continue
                    text = extract_text(file_path)
                    if text and text.strip():
                        docs_from_file = [Document(page_content=text, metadata={
                                                   "source": os.path.basename(file_path)})]
                except Exception as e:
                    # self.logger.error(f"Failed to extract text from PDF {file_path}: {e}") # Requires logger setup
                    # Temporary print
                    print(f"Failed to extract text from PDF {file_path}: {e}")
                    continue  # Skip this file on error
            elif file_type == "txt":  # Assuming other types are text-based
                try:
                    # Ensure file_path exists and is a file
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        self.logger.warning(
                            f"Text file not found or is not a file: {file_path}. Skipping.")
                        continue
                    loader = TextLoader(file_path, encoding="utf-8")
                    loaded_docs_segment = loader.load()
                    if loaded_docs_segment:
                        docs_from_file = loaded_docs_segment
                except Exception as e:
                    # self.logger.error(f"Failed to load text file {file_path}: {e}") # Requires logger setup
                    # Temporary print
                    print(f"Failed to load text file {file_path}: {e}")
                    continue  # Skip this file on error
            else:
                # self.logger.warning(f"Unsupported file type \'{file_type}\' for {file_path}. Skipping.")
                print(
                    f"Unsupported file type \'{file_type}\' for {file_path}. Skipping.")
                continue

            all_loaded_docs.extend(docs_from_file)

        if not all_loaded_docs:
            # This means no documents were successfully loaded from any of the provided files.
            # Vectorstore and retriever will remain None.
            # self.chunks will be empty.
            # Consider raising ValueError or logging.
            print(
                "No documents were successfully loaded from any provided files. RAG index will be empty.")
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100)
        self.chunks = splitter.split_documents(
            all_loaded_docs)  # Split all aggregated docs

        if not self.chunks:
            # This means content was loaded but produced no chunks.
            # Consider raising ValueError or logging.
            print(
                "Aggregated content yielded no processable text chunks. RAG index will be empty.")
            return

        embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name)
        self.vectorstore = FAISS.from_documents(self.chunks, embeddings)
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
        llm = GroqLangChainLLM(model=self.model)
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=self.retriever,
            return_source_documents=True
        )

    def retrieve_docs(self, query: str) -> List[Document]:
        """Retrieves relevant documents from the vector store."""
        if not self.retriever:
            return []
        return self.retriever.get_relevant_documents(query)


class ChatService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Cache RAG instances by chat_id (for Part 2 - Manage RAG Context)
        self.rag_cache = {}

    async def get_youtube_agent_response(self, query: str, chat_history: List[Dict[str, str]]):
        """
        Runs the YouTube agent for a given query and returns the result.
        This is an async wrapper around the synchronous agent execution.
        """
        self.logger.info(f"Passing query to YouTube agent: {query}")
        try:
            # Use sync_to_async to run the synchronous agent function in an async context
            response = await sync_to_async(run_youtube_agent, thread_sensitive=False)(query, chat_history)
            return response
        except Exception as e:
            self.logger.error(
                f"Error calling YouTube agent via sync_to_async: {e}", exc_info=True)
            return "An error occurred while communicating with the YouTube agent."

    def get_files_rag(self, chat_id):
        """Return the cached RAG for this chat, if any. (Used by Part 2: Manage RAG Context)"""
        return self.rag_cache.get(chat_id)

    def build_rag(self, file_path, file_ext, chat_id=None):
        """Builds a RAG index from a file_path. (Used by Part 2: Manage RAG Context)"""
        rag = LangChainRAG(
            model="llama3-8b-8192")  # Consider making model configurable
        rag.build_index(file_path, file_type=file_ext)
        if chat_id:
            self.rag_cache[chat_id] = rag
        return rag

    def extract_text_from_uploaded_file(self, uploaded_file, max_chars=15000):
        filename = uploaded_file.name
        text_content = ""
        was_truncated = False
        original_char_count = 0

        file_extension = os.path.splitext(filename)[1].lower()

        try:
            extracted_text_for_counting = ""
            if file_extension == ".pdf":
                uploaded_file.seek(0)
                raw_text = extract_text(uploaded_file.file)
                extracted_text_for_counting = raw_text.strip() if raw_text else ""
            elif file_extension == ".txt":
                uploaded_file.seek(0)
                raw_bytes = uploaded_file.read()
                extracted_text_for_counting = raw_bytes.decode(
                    'utf-8', errors='replace').strip()
            else:
                extracted_text_for_counting = f"[Unsupported file type: {file_extension}. Only .pdf and .txt are currently supported for direct text extraction.]"

            original_char_count = len(extracted_text_for_counting)

            if original_char_count > max_chars:
                text_content = extracted_text_for_counting[:max_chars]
                was_truncated = True
            else:
                text_content = extracted_text_for_counting

        except Exception as e:
            self.logger.error(
                f"Error extracting text from {filename}: {e}", exc_info=True)
            text_content = f"[Error extracting text from file: {filename}. Please try again or ensure the file is valid.]"
            # In case of error, original_char_count will reflect the length of the source before error,
            # or 0 if error happened very early. was_truncated is False.
            # Let's set original_char_count to 0 if an error occurs during extraction itself.
            # Or consider len(text_content) if error message is informative
            original_char_count = 0
            was_truncated = False

        return {
            'filename': filename,
            # This is the (potentially truncated) text
            'text_content': text_content,
            'was_truncated': was_truncated,
            'original_char_count': original_char_count,
            'final_char_count': len(text_content),
        }

    def process_file(self, uploaded_file):
        """
        Save uploaded file (for Part 2 - RAG Context) and return its path and extension.
        This method is for files intended for persistent RAG indexing.
        """
        if not uploaded_file:
            return "", ""
        file_name = uploaded_file.name
        file_ext = file_name.split('.')[-1].lower()
        # For Part 2, this save_dir should be more robust, e.g., media/rag_files/<chat_id>/
        save_dir = "uploaded_files_for_rag"
        os.makedirs(save_dir, exist_ok=True)

        # Consider using Django's FileSystemStorage for unique names if not using a model's FileField
        # This could have naming collisions
        file_path = os.path.join(save_dir, file_name)
        with default_storage.open(file_path, "wb") as f:  # Use default_storage
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        return file_path, file_ext

    def enforce_token_limit(self, messages, max_tokens=6000):
        from langchain.prompts import PromptTemplate
        from langchain.prompts.example_selector import LengthBasedExampleSelector

        if not messages:
            return messages

        HARD_MAX_TOKENS_API = 5800  # Slightly less than the observed 6000 limit
        SAFETY_BUFFER = 250       # Additional buffer for safety

        system_msg_list = [msg for msg in messages if msg["role"] == "system"]
        user_msg_list = [msg for msg in messages if msg["role"] == "user"]

        # Examples are historical messages (assistant, and user messages except the last one)
        examples = [
            msg for msg in messages
            if msg["role"] not in ("system", "user") or (user_msg_list and msg != user_msg_list[-1])
        ]

        if not system_msg_list or not user_msg_list:
            self.logger.warning(
                "[enforce_token_limit] Missing system or current user message. Returning messages as is, but this might lead to errors.")
            # Fallback: just return messages, hoping for the best, or implement simple truncation if absolutely needed.
            # For now, this state should ideally not be reached in normal operation.
            return messages

        system_msg = system_msg_list[0]
        # Work with a copy to allow modification
        current_user_msg = user_msg_list[-1].copy()

        example_prompt = PromptTemplate(
            input_variables=["role", "content"],
            # Simplified, role is handled by LLM API
            template="{role}: {content}"
        )

        # Calculate tokens for system and current user message
        system_tokens = self._count_tokens([system_msg], example_prompt)
        current_user_tokens_original = self._count_tokens(
            [current_user_msg], example_prompt)

        self.logger.info(
            f"[enforce_token_limit] Initial token counts: System={system_tokens}, CurrentUser(Original)={current_user_tokens_original}")

        # Check if current_user_msg content needs truncation
        # Available tokens for current_user_msg = HARD_MAX_TOKENS_API - system_tokens - SAFETY_BUFFER
        available_for_current_user = HARD_MAX_TOKENS_API - system_tokens - SAFETY_BUFFER
        if current_user_tokens_original > available_for_current_user:
            self.logger.warning(
                f"[enforce_token_limit] Current user message content is too large "
                f"({current_user_tokens_original} tokens) for available space ({available_for_current_user} tokens). "
                f"It will be truncated."
            )
            # Estimate character limit based on token ratio (very approximate)
            # Assuming 1 token ~ 4 chars on average, and our _count_tokens uses 1.4x words.
            # So, num_words = tokens / 1.4. Chars ~ (tokens / 1.4) * avg_word_len (e.g., 5)
            # Target chars = (available_for_current_user / 1.4) * 5 (avg word length)
            # This is still very rough. A simpler approach: reduce by proportion.
            if current_user_tokens_original > 0:  # Avoid division by zero
                proportion_to_keep = available_for_current_user / current_user_tokens_original
                # 0.9 for extra safety
                new_char_length = int(
                    len(current_user_msg["content"]) * proportion_to_keep * 0.9)
                current_user_msg["content"] = current_user_msg["content"][:new_char_length]
                current_user_tokens = self._count_tokens(
                    [current_user_msg], example_prompt)
                self.logger.info(
                    f"[enforce_token_limit] CurrentUser(Truncated) to {current_user_tokens} tokens, new char length {new_char_length}.")
            else:
                current_user_tokens = 0  # Should not happen if content was large
        else:
            current_user_tokens = current_user_tokens_original

        fixed_messages_tokens = system_tokens + current_user_tokens

        max_len_for_examples = HARD_MAX_TOKENS_API - \
            fixed_messages_tokens - SAFETY_BUFFER

        if max_len_for_examples < 0:
            max_len_for_examples = 0  # No space for examples
            self.logger.warning(
                f"[enforce_token_limit] No space available for historical examples after accounting for "
                f"system ({system_tokens}), current user ({current_user_tokens}), and safety buffer ({SAFETY_BUFFER}). "
                f"Total allocated: {fixed_messages_tokens + SAFETY_BUFFER}."
            )

        selector = LengthBasedExampleSelector(
            examples=examples,
            example_prompt=example_prompt,
            max_length=max_len_for_examples  # This is in estimated tokens
        )

        self.logger.info(
            f"[enforce_token_limit] System tokens: {system_tokens}")
        self.logger.info(
            f"[enforce_token_limit] Current user tokens (after potential truncation): {current_user_tokens}")
        self.logger.info(
            f"[enforce_token_limit] Max length for selector (history examples): {max_len_for_examples}")
        self.logger.info(
            f"[enforce_token_limit] Original history length (examples): {len(examples)}")

        selected_examples = selector.select_examples(
            {})  # Pass empty dict as input_variables
        self.logger.info(
            f"[enforce_token_limit] Selected history length (selected_examples): {len(selected_examples)}")

        trimmed_messages = [system_msg] + \
            selected_examples + [current_user_msg]

        final_estimated_tokens = self._count_tokens(
            trimmed_messages, example_prompt)
        self.logger.info(
            f"[enforce_token_limit] Total messages sent to LLM: {len(trimmed_messages)}, Final estimated tokens: {final_estimated_tokens} (Targeting < {HARD_MAX_TOKENS_API})")

        if final_estimated_tokens >= HARD_MAX_TOKENS_API:
            self.logger.error(
                f"[enforce_token_limit] CRITICAL: Final estimated tokens ({final_estimated_tokens}) "
                f"still exceed or meet the hard API limit ({HARD_MAX_TOKENS_API}) despite truncation efforts. "
                f"This indicates a flaw in token estimation or buffer settings."
            )
            # Potentially raise an error here or try more aggressive truncation if this happens often.

        return trimmed_messages

    def _count_tokens(self, messages, prompt_template):
        total = 0
        # Using 1.4 as a heuristic multiplier for word count to token count.
        # Average token length is often less than a full word.
        TOKEN_ESTIMATION_MULTIPLIER = 1.4
        for msg in messages:
            try:
                # Format the message using the template (which only uses 'content' and 'role')
                # then split by space to get word count, then multiply.
                formatted_msg_content = prompt_template.format(
                    **msg)  # Make sure msg has role and content
                word_count = len(formatted_msg_content.split())
                estimated_tokens = int(
                    word_count * TOKEN_ESTIMATION_MULTIPLIER)
                total += estimated_tokens
            except KeyError:
                self.logger.warning(
                    f"Message missing role/content for token counting: {msg}")
            except Exception as e:
                self.logger.error(
                    f"Error counting tokens for message {msg}: {e}", exc_info=True)
        return total

    async def get_completion(self, messages, query=None, files_rag=None, max_tokens=6500, chat_id=None, is_new_chat=False, attached_file_name=None, temperature=0.7):
        # Keep client instantiation local if it has state issues with async
        groq_client_local = Groq()

        if is_new_chat:
            llm_messages = [{'role': msg['role'],
                             'content': msg['content']} for msg in messages]
            # This part should be sync or wrapped if get_completion is to be truly async.
            # For now, assuming it's called in a context that can handle this if it blocks briefly,
            # or that this path is less critical for full async behavior if it's just for the first message.
            completion = (groq_client_local.chat.completions.create)(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            return completion.choices[0].message.content

        current_messages_copy = [msg.copy()
                                 for msg in messages]  # Work with a copy

        context_str = ""
        rag_output = ""
        if files_rag and query:
            # Assuming files_rag.retrieve is CPU bound or already async; if sync I/O, wrap it
            # For now, let's assume it's okay or needs to be made async separately if it blocks.
            # retrieved_context_val = await sync_to_async(files_rag.retrieve)(query) # Example if it needed wrapping
            retrieved_context_val = files_rag.retrieve_docs(query)  # Original
            rag_output = retrieved_context_val
            self.logger.info(
                f"RAG output HERE!!!!!!!!!!! {str(rag_output)[:500]}...")
            if retrieved_context_val:
                context_str += str(retrieved_context_val)

        if context_str.strip():
            rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"
            if current_messages_copy and current_messages_copy[-1]["role"] == "user":
                original_user_content = current_messages_copy[-1]["content"]
                context_preamble = f"Relevant context from your uploaded documents ({rag_info_source}):\n\"\"\"{context_str}\"\"\"\n---\nOriginal query follows:\n"
                current_messages_copy[-1]["content"] = context_preamble + \
                    original_user_content
            else:
                self.logger.warning(
                    "Could not find user message to prepend RAG context to.")

        trimmed_messages = self.enforce_token_limit(
            current_messages_copy, max_tokens=max_tokens)

        # Wrap the synchronous SDK call
        completion = await sync_to_async(groq_client_local.chat.completions.create)(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        # Logic for RAG output vs LLM completion seems to have an issue here.
        # If rag_output exists, it should likely be returned, not the LLM completion directly unless RAG modifies the query for LLM.
        # This part of the logic needs review from original implementation if RAG output should take precedence.
        # For now, mimicking the original structure but noting this potential issue.
        if rag_output:  # This was the original logic, implies rag_output is preferred IF it exists
            self.logger.info(f"In rag_output - returning RAG output directly.")
            return rag_output
        else:
            self.logger.info(f"No RAG output, returning LLM completion.")
            return completion.choices[0].message.content

    async def stream_completion(self, messages, query=None, files_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        groq_client_local = Groq()  # Keep client instantiation local

        if is_new_chat:
            llm_messages = [{'role': msg['role'],
                             'content': msg['content']} for msg in messages]

            return groq_client_local.chat.completions.create(  # Keeping this sync as it returns a generator
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                stream=True,
            )

        current_messages_copy = [msg.copy()
                                 for msg in messages]  # Work with a copy

        if files_rag and query:
            # Create a history string for better retrieval context
            history_str = "\n".join(
                [f"{m['role']}: {m['content']}" for m in current_messages_copy[:-1]])
            # Combine history with the current query for a more informed search
            full_query_for_retrieval = f"Conversation_history: {history_str}\n\nQuestion: {query}"

            # 1. Retrieve documents
            retrieved_docs = await sync_to_async(files_rag.retrieve_docs)(full_query_for_retrieval)

            if retrieved_docs:
                # 2. Augment the prompt
                context_str = "\n\n".join(
                    [doc.page_content for doc in retrieved_docs])
                rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"

                if current_messages_copy and current_messages_copy[-1]["role"] == "user":
                    original_user_content = current_messages_copy[-1]["content"]
                    # Create the augmented prompt
                    context_preamble = (
                        f"Use the following context from your uploaded documents ({rag_info_source}) to answer the question.\n\n"
                        f"--- CONTEXT ---\n{context_str}\n--- END CONTEXT ---\n\n"
                        f"Based on the context, answer this question: {original_user_content}"
                    )
                    current_messages_copy[-1]["content"] = context_preamble
                    self.logger.info(
                        "Augmented the user prompt with RAG context.")

        trimmed_messages = self.enforce_token_limit(
            current_messages_copy, max_tokens=max_tokens)

        # 3. Generate the streaming response
        return groq_client_local.chat.completions.create(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=True,
        )

    def save_file(self, chat_id, uploaded_file):
        if uploaded_file:
            return default_storage.save(
                f'media/chat_uploads/{chat_id}/{uploaded_file.name}',
                uploaded_file
            )
        return None

    def create_message(self, chat, role, content):
        return Message.objects.create(
            chat=chat,
            role=role,
            content=content
        )

    def get_chat_history(self, chat, limit=20):
        return list(chat.messages.all().order_by('created_at'))[-limit:]

    def update_chat_title(self, chat, title_text=None):
        if not title_text:
            return
        chat.title = title_text[:50] + ('...' if len(title_text) > 50 else '')
        chat.save()

    async def generate_diagram_image(self, chat_history_messages, user_query, chat_id, user_id):
        self.logger.info(
            f"Starting diagram generation for chat {chat_id}, user query: {user_query}")

        messages_for_description = chat_history_messages + \
            [{"role": "user", "content": user_query}]
        messages_for_description.insert(
            0, {"role": "system", "content": prompt_description})
        self.logger.info(
            f"Messages for description LLM call (first few): {str(messages_for_description)[:200]}")

        try:
            structured_description_content = flashcard_model.generate_content(
                f"{prompt_description}\n\nGenerate a structured explanation for: {user_query}")
            structured_description_content = structured_description_content.text.strip()
            self.logger.info(
                f"Received structured description: {structured_description_content[:200]}...")
            if not structured_description_content or not structured_description_content.strip():
                self.logger.error(
                    "LLM failed to generate a structured description.")
                return None
        except Exception as e:
            self.logger.error(
                f"Error getting structured description from LLM: {e}", exc_info=True)
            return None

        self.logger.info(
            f"Messages for Graphviz LLM call (system prompt length: {len(prompt_code_graphviz)}, user content length: {len(structured_description_content) if structured_description_content else 0})")

        try:
            graphviz_code_response = flashcard_model.generate_content(
                f"{prompt_code_graphviz}\n\nGenerate a structured explanation for: {structured_description_content}")
            graphviz_code_response = graphviz_code_response.text.strip()
            self.logger.info(
                f"Received Graphviz code response (first 200 chars): {graphviz_code_response[:200] if graphviz_code_response else 'Empty response'}...")
            if not graphviz_code_response or not graphviz_code_response.strip():
                self.logger.error(
                    "LLM failed to generate Graphviz code (empty response).")
                return None
        except Exception as e:
            self.logger.error(
                f"Error getting Graphviz code from LLM: {e}", exc_info=True)
            return None

        # We'll take the response as is, after stripping whitespace.
        graphviz_code = graphviz_code_response.strip()

        # Extract Python code from markdown block
        # Try ```python ... ``` first
        python_match = re.search(
            r"```python\s*\n(.*?)\n```", graphviz_code, re.DOTALL)
        if python_match:
            graphviz_code = python_match.group(1).strip()
            self.logger.info("Extracted code from ```python block.")
        else:
            # Try generic ``` ... ``` if ```python block is not found
            generic_match = re.search(
                r"```\s*\n(.*?)\n```", graphviz_code, re.DOTALL)
            if generic_match:
                graphviz_code = generic_match.group(1).strip()
                self.logger.info("Extracted code from generic ``` block.")
            else:
                # If no markdown block found, it might be raw code.
                self.logger.warning(
                    "Could not find markdown code block. Assuming response might be raw code or require import-based cleaning.")
                # The following "find 'import graphviz'" logic will attempt to find the code start if markdown was missed.
                # This is a fallback and primarily handles leading non-code text if no markdown was used.
                # The regex extraction is the primary mechanism for handling text outside of correctly used markdown blocks.

        # If code was NOT extracted from markdown (i.e., no fences found), try to find the start of Python code by 'import graphviz'
        # This helps clean up potential leading non-code text if the LLM didn't use markdown.
        if not python_match and not generic_match:
            lines = graphviz_code.split('\n')
            actual_code_start_index = -1
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if stripped_line.startswith("from graphviz import") or stripped_line.startswith("import graphviz"):
                    actual_code_start_index = i
                    break

            if actual_code_start_index != -1:
                # If 'import' is found, take everything from that line onwards and strip any trailing whitespace/newlines.
                graphviz_code = '\n'.join(
                    lines[actual_code_start_index:]).strip()
                self.logger.info(
                    "Found code start using 'import graphviz' after no markdown blocks were detected.")
            else:
                # This means no markdown and no 'import graphviz' found. Code is likely bad or not Python/Graphviz.
                self.logger.warning(
                    f"[generate_diagram_image] Could not find markdown blocks or 'import graphviz'. Code is likely not valid Python/Graphviz. Proceeding with potentially unclean code: {graphviz_code[:200]}...")

        self.logger.info(
            f"Cleaned Graphviz code (first 100 chars): {graphviz_code[:100]}...")

        # More lenient check - only require import and Digraph creation
        # This check is now more critical as graphviz_code might be empty if regex found nothing and no import line was present
        if not graphviz_code or not ("graphviz" in graphviz_code and "Digraph(" in graphviz_code):
            self.logger.error(
                f"Generated Graphviz code does not appear to be valid or is empty. Preview: {graphviz_code[:500]}")
            return None

        # Add fallback .render() call if missing
        if ".render(" not in graphviz_code:
            self.logger.info("Adding fallback .render() call to Graphviz code")
            # Add render call to the end of the code
            graphviz_code += "\n\n# Fallback render call\ng.render('diagram_output', view=False, cleanup=True)"

        # Pre-process the code to handle common issues
        # Remove invalid 'parent' attribute which is a common mistake in the generated code
        # Reverted to more general parent removal, using r"..." for regex string
        graphviz_code = re.sub(
            r"parent\s*=\s*['\"].*?['\"]", '', graphviz_code)
        self.logger.info(
            f"Pre-processed Graphviz code (first 300 chars): {graphviz_code[:300]}...")

        async def _render_graphviz_sync(code_to_execute, chat_model_instance, user_model_instance, topic_name_from_query, structured_description_content_for_fix):
            current_code = code_to_execute
            local_namespace = {}
            exec_globals = {"graphviz": graphviz, "Digraph": graphviz.Digraph,
                            "os": os, "__builtins__": __builtins__}

            # Create temp directory
            debug_dir = os.path.join(settings.MEDIA_ROOT, "temp_diagram_debug")
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = int(time.time())

            # Set system encoding to UTF-8 for this process
            if sys.platform.startswith('win'):
                # On Windows, we need to set the console encoding
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')

            for attempt in range(3):
                self.logger.info(
                    f"--- Graphviz Execution Attempt {attempt + 1}/3 ---")

                # Save .gv file with UTF-8 encoding
                gv_file_path = os.path.join(
                    debug_dir, f"diagram_attempt_{timestamp}_{attempt + 1}.gv")
                try:
                    with open(gv_file_path, "w", encoding='utf-8') as f_gv:
                        f_gv.write(current_code)
                    self.logger.info(
                        f"Saved GV code for attempt {attempt + 1} to: {gv_file_path}")
                except Exception as e_gv_save:
                    self.logger.error(f"Error saving .gv file: {e_gv_save}")
                    # Try alternative encoding if UTF-8 fails
                    try:
                        with open(gv_file_path, "w", encoding=self.get_system_encoding()) as f_gv:
                            f_gv.write(current_code)
                        self.logger.info(
                            f"Saved GV code with system encoding for attempt {attempt + 1}")
                    except Exception as e_gv_save_alt:
                        self.logger.error(
                            f"Error saving .gv file with system encoding: {e_gv_save_alt}")
                        continue

                try:
                    # Execute the code
                    exec(current_code, exec_globals, local_namespace)

                    # Find the graph object
                    graph_object = None
                    for name, val in local_namespace.items():
                        if isinstance(val, graphviz.Digraph):
                            graph_object = val
                            self.logger.info(f"Found graph object: {name}")
                            break

                    if not graph_object:
                        self.logger.error(
                            "No Digraph object found in the executed code")
                        continue

                    # Try to generate the image
                    try:
                        graph_object.format = 'png'

                        # Set font settings to support emoji
                        # Windows emoji font
                        graph_object.attr('node', fontname='Segoe UI Emoji')
                        graph_object.attr('edge', fontname='Segoe UI Emoji')

                        # Try to generate the image
                        image_bytes = None
                        try:
                            image_bytes = graph_object.pipe()
                        except Exception as pipe_error:
                            self.logger.warning(
                                f"Pipe failed, trying render method: {pipe_error}")
                            # Fallback to render method
                            temp_filename = f"temp_diagram_{timestamp}_{attempt}"
                            rendered_path = graph_object.render(
                                filename=temp_filename, directory=debug_dir, view=False, cleanup=True)
                            if rendered_path and os.path.exists(rendered_path):
                                with open(rendered_path, 'rb') as f:
                                    image_bytes = f.read()
                                os.remove(rendered_path)
                            else:
                                raise Exception(
                                    "Failed to generate image using render method")

                        if not image_bytes:
                            self.logger.error("No image data generated")
                            continue

                        # Save to DiagramImage model
                        safe_topic_filename = sanitize_filename(
                            topic_name_from_query).replace(' ', '_') + ".png"

                        diagram_image_instance = await sync_to_async(DiagramImage.objects.create)(
                            chat=chat_model_instance,
                            user=user_model_instance,
                            image_data=image_bytes,
                            filename=safe_topic_filename,
                            content_type='image/png'
                        )

                        self.logger.info(
                            f"✅ Diagram saved successfully with ID: {diagram_image_instance.id}")
                        return diagram_image_instance.id

                    except Exception as e:
                        self.logger.error(f"Error generating image: {str(e)}")
                        continue

                except Exception as e:
                    self.logger.error(f"Error executing code: {str(e)}")
                    if attempt == 2:  # Last attempt
                        return None

                    # Try to get fixed code from LLM
                    try:
                        fix_prompt_content = prompt_fix_code.format(
                            topic=topic_name_from_query,
                            description=structured_description_content_for_fix,
                            erroneous_code=current_code,
                            error_message=str(e)
                        )

                        fixed_code_response = await self.get_completion(
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant that fixes Python Graphviz code."},
                                {"role": "user", "content": fix_prompt_content}
                            ],
                            max_tokens=6000,
                            chat_id=chat_model_instance.id,
                            temperature=0.0
                        )

                        if fixed_code_response and fixed_code_response.strip():
                            current_code = fixed_code_response.strip()
                        else:
                            self.logger.error(
                                "No fixed code received from LLM")
                            return None

                    except Exception as llm_fix_exc:
                        self.logger.error(
                            f"Error getting fixed code: {str(llm_fix_exc)}")
                        return None

            return None

        try:
            # Fetch Chat and User model instances to pass to _render_graphviz_sync
            chat_instance = await sync_to_async(Chat.objects.get)(id=chat_id)
            # Changed User to CustomUser
            user_instance = await sync_to_async(CustomUser.objects.get)(id=user_id)

            diagram_image_id = await _render_graphviz_sync(
                graphviz_code,
                chat_instance,
                user_instance,
                user_query,  # topic_name_from_query
                structured_description_content  # structured_description_content_for_fix
            )
            return diagram_image_id  # This will be the ID or None
        except Chat.DoesNotExist:
            self.logger.error(
                f"Chat with ID {chat_id} not found for diagram generation.")
            return None
        except CustomUser.DoesNotExist:  # Changed User to CustomUser
            self.logger.error(
                f"User with ID {user_id} not found for diagram generation.")
            return None
        except Exception as e_render_async_call:
            self.logger.error(
                f"Error during top-level call for Graphviz rendering: {type(e_render_async_call).__name__} - {e_render_async_call}", exc_info=True)
            return None

    async def generate_quiz_from_query(self, chat_history_messages: List[Dict[str, str]], user_query: str, chat_id: str, **kwargs) -> Dict[str, Any]:
        """
        Generates a quiz based on the conversation history, with a focus on the user's specific query.
        (Used by the QuizTool agent)
        """
        self.logger.info(
            f"Starting query-focused quiz generation for chat {chat_id} on topic: '{user_query}'")

        # Add the user's specific query to the history to ensure it's part of the context
        history_with_query = chat_history_messages + \
            [{"role": "user", "content": user_query}]
        content_text = "\n".join(
            [msg['content']
                for msg in history_with_query if msg.get('content')]
        )

        if len(content_text) < 100:
            self.logger.warning(
                "Not enough conversation content to generate a quiz.")
            return {"error": "Not enough conversation content to generate a quiz."}

        focus_instruction = f"The user has specifically asked to be quizzed on: '{user_query}'. Please create questions that are primarily focused on this topic, using the provided conversation as context to find relevant information."

        prompt = f"""
        You are a helpful assistant that creates quizzes.
        {focus_instruction}
        
        Create at least 2 multiple-choice quizzes (4 options per question) based on the following conversation.
        For each question, use this HTML structure:
        <div class="quiz-question" data-correct="B">
          <div class="font-semibold mb-1">What is 2+2?</div>
          <form>
            <label><input type="radio" name="q1" value="A"> 3</label><br>
            <label><input type="radio" name="q1" value="B"> 4</label><br>
            <label><input type="radio" name="q1" value="C"> 5</label><br>
            <label><input type="radio" name="q1" value="D"> 6</label><br>
            <button type="submit" class="mt-1.5 px-2 py-1 bg-blue-600 text-white rounded">Check Answer</button>
          </form>
          <div class="quiz-feedback mt-1.5"></div>
        </div>
        Replace the question, answers, and correct value as appropriate.
        **CRITICAL: Output ONLY the HTML for the quiz. Do NOT include any explanations, introductory text, or content outside the HTML structure.**
        **Do NOT add phrases like "Here's your quiz" or "Based on the conversation" - output ONLY the quiz HTML.**
        
        Conversation for Context:
        {content_text}
        """

        try:
            quiz_html_response = await self.get_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000
            )

            # More robust extraction to separate text from HTML
            return self._extract_quiz_content(quiz_html_response, user_query)

        except Exception as e:
            self.logger.error(
                f"Query-focused quiz generation call failed: {e}", exc_info=True)
            return {"error": f"Quiz generation failed: {str(e)}"}

    async def generate_quiz(self, chat_history_messages: List[Dict[str, str]], chat_id: str, **kwargs) -> Dict[str, Any]:
        """
        Generates a general quiz based on the conversation history.
        (Used by the manual 'Generate Quiz' button)
        """
        self.logger.info(
            f"Starting general quiz generation for chat {chat_id}")

        # Combine conversation history into a single text block
        content_text = "\n".join(
            [msg['content']
                for msg in chat_history_messages if msg.get('content')]
        )

        # Ensure there is enough content to generate a meaningful quiz
        if len(content_text) < 200:
            self.logger.warning(
                "Not enough conversation content to generate a quiz.")
            return {"error": "Not enough conversation content to generate a quiz."}

        # Define the prompt for the AI model
        prompt = f"""
        Create at least 2 multiple-choice quizzes (4 options per question) based on the following conversation's relevant scientific information only, related to the learning.
        For each question, use this HTML structure:
        <div class="quiz-question" data-correct="B">
          <div class="font-semibold mb-1">What is 2+2?</div>
          <form>
            <label><input type="radio" name="q1" value="A"> 3</label><br>
            <label><input type="radio" name="q1" value="B"> 4</label><br>
            <label><input type="radio" name="q1" value="C"> 5</label><br>
            <label><input type="radio" name="q1" value="D"> 6</label><br>
            <button type="submit" class="mt-1.5 px-2 py-1 bg-blue-600 text-white rounded">Check Answer</button>
          </form>
          <div class="quiz-feedback mt-1.5"></div>
        </div>
        Replace the question, answers, and correct value as appropriate.
        **CRITICAL: Output ONLY the HTML for the quiz. Do NOT include any explanations, introductory text, or content outside the HTML structure.**
        **Do NOT add phrases like "Here's your quiz" or "Based on the conversation" - output ONLY the quiz HTML.**
        
        Conversation:

        {content_text}
        """

        try:
            # Call the AI model to get the quiz HTML
            quiz_html_response = await self.get_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000
            )

            # More robust extraction to separate text from HTML
            return self._extract_quiz_content(quiz_html_response, "conversation content")

        except Exception as e:
            self.logger.error(
                f"Quiz generation call failed: {e}", exc_info=True)
            return {"error": f"Quiz generation failed: {str(e)}"}

    def _extract_quiz_content(self, llm_response: str, topic: str) -> Dict[str, Any]:
        """
        Extract and separate quiz HTML from any accompanying text content.
        Ensures only pure HTML goes to quiz_html and text goes to content.
        """
        try:
            # Remove any markdown code blocks first
            response_text = llm_response.strip()
            if response_text.startswith("```") and response_text.endswith("```"):
                # Remove markdown code fences
                lines = response_text.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = '\n'.join(lines)

            # Look for quiz HTML structure
            html_match = re.search(
                r'(<div class="quiz-question".*)', response_text, re.DOTALL)

            if html_match:
                # Extract HTML content
                quiz_html = html_match.group(1).strip()

                # Extract any text that appears before the HTML (if any)
                text_before_html = response_text[:html_match.start()].strip()

                # Clean up the HTML to ensure it only contains quiz elements
                quiz_html = self._clean_quiz_html(quiz_html)

                # Prepare result
                result = {"quiz_html": quiz_html}

                # Add any explanatory text to content if it exists and seems meaningful
                if text_before_html and len(text_before_html) > 10:
                    # Filter out common AI-generated prefixes
                    filtered_text = self._filter_ai_prefixes(text_before_html)
                    if filtered_text:
                        result["content"] = filtered_text

                self.logger.info(
                    f"Extracted quiz HTML ({len(quiz_html)} chars) and content ({len(result.get('content', '')) if result.get('content') else 0} chars)")
                return result
            else:
                # No proper HTML structure found
                self.logger.warning(
                    f"Could not find quiz HTML structure in LLM response: {response_text[:200]}...")

                # Check if there's any content that could be salvaged
                if "quiz" in response_text.lower() or "question" in response_text.lower():
                    # Try to use the raw response as HTML (fallback)
                    return {
                        "quiz_html": response_text,
                        "content": f"Generated quiz based on {topic}"
                    }
                else:
                    return {"error": "No valid quiz content generated"}

        except Exception as e:
            self.logger.error(
                f"Error extracting quiz content: {e}", exc_info=True)
            return {"error": f"Failed to process quiz content: {str(e)}"}

    def _clean_quiz_html(self, html_content: str) -> str:
        """
        Clean the quiz HTML to ensure it only contains quiz-related elements.
        Remove any text content that doesn't belong in HTML.
        """
        try:
            # Remove any text that appears after the last </div> tag
            last_div_end = html_content.rfind('</div>')
            if last_div_end != -1:
                # Check if there's significant text after the last </div>
                text_after = html_content[last_div_end + 6:].strip()
                if text_after and not text_after.startswith('<'):
                    # Remove trailing text that's not HTML
                    html_content = html_content[:last_div_end + 6]

            # Remove any leading text that's not HTML
            first_div_start = html_content.find('<div')
            if first_div_start > 0:
                leading_text = html_content[:first_div_start].strip()
                if leading_text and not leading_text.startswith('<'):
                    # Remove leading text that's not HTML
                    html_content = html_content[first_div_start:]

            return html_content.strip()

        except Exception as e:
            self.logger.error(f"Error cleaning quiz HTML: {e}")
            return html_content

    def _filter_ai_prefixes(self, text: str) -> str:
        """
        Filter out common AI-generated prefixes and return meaningful content.
        """
        # Common AI-generated prefixes to remove
        ai_prefixes = [
            "here's your quiz",
            "here is your quiz",
            "based on the conversation",
            "quiz:",
            "here are the questions",
            "below is the quiz",
            "i've created a quiz",
            "the quiz is ready",
        ]

        text_lower = text.lower().strip()

        # Remove common prefixes
        for prefix in ai_prefixes:
            if text_lower.startswith(prefix):
                return ""  # Return empty string for these common prefixes

        # If text is very short or seems like a prefix, ignore it
        if len(text) < 15 or any(phrase in text_lower for phrase in ["here's", "here is", "below"]):
            return ""

        return text.strip()

    def get_system_encoding(self):
        """Get the system's preferred encoding, defaulting to UTF-8 if not available."""
        try:
            return locale.getpreferredencoding()
        except:
            return 'utf-8'
