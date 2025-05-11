import os
import datetime
import json
from .models import Message
from .preference_service import PreferenceService
from django.core.files.storage import default_storage
from io import StringIO
import logging
import copy
from functools import lru_cache

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

    def build_index(self, file_paths_and_types): # Expects a list of tuples: [(file_path, file_type), ...]
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
                        self.logger.warning(f"PDF file not found or is not a file: {file_path}. Skipping.")
                        continue
                    text = extract_text(file_path) 
                    if text and text.strip():
                        docs_from_file = [Document(page_content=text, metadata={"source": os.path.basename(file_path)})]
                except Exception as e:
                    # self.logger.error(f"Failed to extract text from PDF {file_path}: {e}") # Requires logger setup
                    print(f"Failed to extract text from PDF {file_path}: {e}") # Temporary print
                    continue # Skip this file on error
            elif file_type == "txt": # Assuming other types are text-based
                try:
                    # Ensure file_path exists and is a file
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        self.logger.warning(f"Text file not found or is not a file: {file_path}. Skipping.")
                        continue
                    loader = TextLoader(file_path, encoding="utf-8")
                    loaded_docs_segment = loader.load()
                    if loaded_docs_segment:
                        docs_from_file = loaded_docs_segment
                except Exception as e:
                    # self.logger.error(f"Failed to load text file {file_path}: {e}") # Requires logger setup
                    print(f"Failed to load text file {file_path}: {e}") # Temporary print
                    continue # Skip this file on error
            else:
                # self.logger.warning(f"Unsupported file type \'{file_type}\' for {file_path}. Skipping.")
                print(f"Unsupported file type \'{file_type}\' for {file_path}. Skipping.")
                continue
            
            all_loaded_docs.extend(docs_from_file)

        if not all_loaded_docs:
            # This means no documents were successfully loaded from any of the provided files.
            # Vectorstore and retriever will remain None.
            # self.chunks will be empty.
            # Consider raising ValueError or logging.
            print("No documents were successfully loaded from any provided files. RAG index will be empty.")
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100)
        self.chunks = splitter.split_documents(all_loaded_docs) # Split all aggregated docs

        if not self.chunks:
            # This means content was loaded but produced no chunks.
            # Consider raising ValueError or logging.
            print("Aggregated content yielded no processable text chunks. RAG index will be empty.")
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

    def retrieve(self, query):
        if not self.qa_chain:
            return ""
        result = self.qa_chain({"query": query})
        return result["result"]


class ChatService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rag_cache = {}  # Cache RAG instances by chat_id (for Part 2 - Manage RAG Context)

    def get_files_rag(self, chat_id):
        """Return the cached RAG for this chat, if any. (Used by Part 2: Manage RAG Context)"""
        return self.rag_cache.get(chat_id)

    def build_rag(self, file_path, file_ext, chat_id=None):
        """Builds a RAG index from a file_path. (Used by Part 2: Manage RAG Context)"""
        rag = LangChainRAG(model="llama3-8b-8192") # Consider making model configurable
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
                extracted_text_for_counting = raw_bytes.decode('utf-8', errors='replace').strip()
            else:
                extracted_text_for_counting = f"[Unsupported file type: {file_extension}. Only .pdf and .txt are currently supported for direct text extraction.]"
            
            original_char_count = len(extracted_text_for_counting)

            if original_char_count > max_chars:
                text_content = extracted_text_for_counting[:max_chars]
                was_truncated = True
            else:
                text_content = extracted_text_for_counting
            
        except Exception as e:
            self.logger.error(f"Error extracting text from {filename}: {e}", exc_info=True)
            text_content = f"[Error extracting text from file: {filename}. Please try again or ensure the file is valid.]"
            # In case of error, original_char_count will reflect the length of the source before error,
            # or 0 if error happened very early. was_truncated is False.
            # Let's set original_char_count to 0 if an error occurs during extraction itself.
            original_char_count = 0 # Or consider len(text_content) if error message is informative
            was_truncated = False

        return {
            'filename': filename,
            'text_content': text_content, # This is the (potentially truncated) text
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
        file_path = os.path.join(save_dir, file_name) # This could have naming collisions
        with default_storage.open(file_path, "wb") as f: # Use default_storage
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        return file_path, file_ext

    def enforce_token_limit(self, messages, max_tokens=6000):
        from langchain.prompts import PromptTemplate
        from langchain.prompts.example_selector import LengthBasedExampleSelector

        if not messages:
            return messages
        
        # Assuming the first message is system, last is current user query.
        # This logic might need adjustment based on exact message structure.
        # For now, keep as is, LengthBasedExampleSelector handles examples.
        system_msg_list = [msg for msg in messages if msg["role"] == "system"]
        user_msg_list = [msg for msg in messages if msg["role"] == "user"]
        examples = [msg for msg in messages if msg["role"] not in ("system", "user") or (msg["role"] == "user" and msg != user_msg_list[-1])]


        if not system_msg_list or not user_msg_list: # Should not happen in normal flow
            # Fallback: just take the last N tokens if structure is unexpected
            # This is a simplification; proper token counting per message is better.
            all_content = " ".join([msg["content"] for msg in messages])
            # A very rough approximation of token count
            if len(all_content.split()) > max_tokens * 0.7: # Target less than max_tokens
                 # This is not ideal, a more sophisticated truncation is needed here
                 # For now, this path is unlikely with current message structure
                 pass # Let LengthBasedExampleSelector handle it if examples are present
            return messages # Or apply a simpler truncation if no examples


        system_msg = system_msg_list[0]
        current_user_msg = user_msg_list[-1] # The latest user message

        example_prompt = PromptTemplate(
            input_variables=["role", "content"],
            template="{role}: {content}"
        )
        
        # Calculate tokens for system and current user message
        fixed_messages_tokens = self._count_tokens([system_msg, current_user_msg], example_prompt)
        
        selector = LengthBasedExampleSelector(
            examples=examples, # Historical messages (assistant, and user messages except the last one)
            example_prompt=example_prompt,
            max_length=max_tokens - fixed_messages_tokens
        )
        self.logger.info(f"[enforce_token_limit] Max length for selector: {max_tokens - fixed_messages_tokens}")
        self.logger.info(f"[enforce_token_limit] Original history length (examples): {len(examples)}")
        selected_examples = selector.select_examples({})
        self.logger.info(f"[enforce_token_limit] Selected history length (selected_examples): {len(selected_examples)}")

        trimmed_messages = [system_msg] + selected_examples + [current_user_msg]
        self.logger.info(f"[enforce_token_limit] Total messages sent to LLM: {len(trimmed_messages)}")
        return trimmed_messages

    def _count_tokens(self, messages, prompt_template):
        total = 0
        for msg in messages:
            try:
                total += len(prompt_template.format(**msg).split())
            except KeyError: # Handle cases where a message might not have role/content
                self.logger.warning(f"Message missing role/content for token counting: {msg}")
        return total

    def get_completion(self, messages, query=None, files_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        if is_new_chat:
            groq_client = Groq()
            llm_messages = [{'role': msg['role'], 'content': msg['content']} for msg in messages]
            completion = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024, # Consider making this configurable
                stream=False,
            )
            return completion.choices[0].message.content
        
        current_messages = [msg for msg in messages] 

        # files_rag is now ONLY explicitly passed for Part 2 (Manage RAG Context)
        # No automatic loading of files_rag based on chat_id here.

        context_str = ""
        rag_output = ""
        if files_rag and query: # files_rag is only used if explicitly passed and query is present
            retrieved_context_val = files_rag.retrieve(query) 
            rag_output = retrieved_context_val
            self.logger.info(f"RAG output HERE!!!!!!!!!!! {str(rag_output)[:500]}...")
            print("=======================================================")
            self.logger.info(f"RAG retrieved_context for query '{query[:100]}...': '{str(retrieved_context_val)[:500]}...'")
            if retrieved_context_val:
                 context_str += str(retrieved_context_val)
        
        if context_str.strip():
            rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"
            
            # Prepend RAG context to the last user message content
            if current_messages and current_messages[-1]["role"] == "user":
                original_user_content = current_messages[-1]["content"]
                
                # Construct the new content with RAG context clearly delineated
                context_preamble = f"Relevant context from your uploaded documents ({rag_info_source}):\\n\"\"\"{context_str}\"\"\"\\n---\\nOriginal query follows:\\n"
                current_messages[-1]["content"] = context_preamble + original_user_content
                self.logger.info(f"Prepended RAG context to user query. New content starts with: {current_messages[-1]['content'][:300]}...")
            else:
                # This case should ideally not happen if current_messages always ends with the user query
                # If it does, we might fall back to inserting a system message or logging an error
                self.logger.warning("Could not find user message to prepend RAG context to. Context will not be used directly in user query.")
                # Fallback: create a system-like message if user message not found (less ideal but better than losing context)
                # context_system_message = {"role": "system", "content": f"Consider the following context{rag_info_source}:\\n{context_str}"}
                # current_messages.insert(-1, context_system_message) # Insert before last message if it's not user, or adapt

        trimmed_messages = self.enforce_token_limit(current_messages, max_tokens=max_tokens)
        
        groq_client = Groq()
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_completion_tokens=1024, # Consider making this configurable
            stream=False,
        )
        if rag_output:
            self.logger.info(f"In rag_output")
            return rag_output
        else:
            print("In completion")
            return completion.choices[0].message.content

    def stream_completion(self, messages, query=None, files_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        if is_new_chat:
            groq_client = Groq()
            llm_messages = [{'role': msg['role'], 'content': msg['content']} for msg in messages]
            return groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024, # Consider making this configurable
                stream=True,
            )
        print("======== Inside stream_completion ===========")
        print(f"messages: {messages}")
        print(f"query: {query}")
        print(f"files_rag: {files_rag}")
        print(f"max_tokens: {max_tokens}")
        print(f"chat_id: {chat_id}")
        print(f"is_new_chat: {is_new_chat}")
        print(f"attached_file_name: {attached_file_name}")
        print("======== Done printing ===========")
        current_messages = [msg for msg in messages]

        # files_rag is now ONLY explicitly passed for Part 2 (Manage RAG Context)
        # No automatic loading of files_rag based on chat_id here.

        context_str = ""
        raggyy = ""
        if files_rag and query: # files_rag is only used if explicitly passed and query is present
            retrieved_context_val = files_rag.retrieve(query) 
            raggyy = retrieved_context_val
            self.logger.info(f"RAG retrieved_context for query '{query[:100]}...': '{str(retrieved_context_val)[:500]}...'")
            if retrieved_context_val:
                 context_str += str(retrieved_context_val)
        
        # chat_history_rag logic completely removed.
        
        if context_str.strip():
            rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"

            # Prepend RAG context to the last user message content
            if current_messages and current_messages[-1]["role"] == "user":
                original_user_content = current_messages[-1]["content"]

                # Construct the new content with RAG context clearly delineated
                context_preamble = f"Relevant context from your uploaded documents ({rag_info_source}):\\n\"\"\"{context_str}\"\"\"\\n---\\nOriginal query follows:\\n"
                current_messages[-1]["content"] = context_preamble + original_user_content
                self.logger.info(f"Prepended RAG context to user query. New content starts with: {current_messages[-1]['content'][:300]}...")

            else:
                self.logger.warning("Could not find user message to prepend RAG context to in stream_completion. Context will not be used directly in user query.")

        trimmed_messages = self.enforce_token_limit(current_messages, max_tokens=max_tokens)
        if raggyy:
            return raggyy
        else:
            groq_client = Groq()
            return groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=trimmed_messages,
                temperature=0.7,
                max_completion_tokens=1024, # Consider making this configurable
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
