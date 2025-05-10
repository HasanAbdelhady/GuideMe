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

    def build_index(self, file_path, file_type="pdf"):
        docs = []
        if file_type == "pdf":
            text = extract_text(file_path) # This extracts all text from the PDF.
            if text and text.strip(): # Check if text was extracted and is not just whitespace
                # Create a single Document object from the entire PDF text.
                # Add metadata for source identification.
                docs = [Document(page_content=text, metadata={"source": os.path.basename(file_path)})]
            # If no text, docs remains empty.
        else: # For .txt and other text-based files
            try:
                loader = TextLoader(file_path, encoding="utf-8")
                loaded_docs = loader.load()
                if loaded_docs: # Ensure loader.load() returned documents
                    docs = loaded_docs
            except Exception as e:
                # Ideally, log this error: logging.error(f"Failed to load text file {file_path}: {e}")
                # For now, docs will remain empty, and the check below will catch it.
                pass # docs remains empty
        print(f"This is the docs: {docs}")
        if not docs:
            raise ValueError(
                f"No text content could be loaded or extracted from {os.path.basename(file_path)}. "
                "The file might be empty, a non-supported format, or PDF extraction yielded no text."
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100)
        self.chunks = splitter.split_documents(docs)

        if not self.chunks:
            # This means content was loaded but produced no chunks.
            raise ValueError(
                f"Content from {os.path.basename(file_path)} loaded, but yielded no processable text chunks. "
                "It might be too short or lack suitable structure for chunking."
            )

        # Embedding and vectorstore
        embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name)
        # This step generates embeddings and builds the FAISS index, which is computationally intensive.
        self.vectorstore = FAISS.from_documents(self.chunks, embeddings)
        print(f"This is the vectorstore: {self.vectorstore}")
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
        print(f"This is the retriever: {self.retriever}")
        # Use GroqLangChainLLM instead of OpenAI
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
        self.rag_cache = {}  # Cache RAG instances by chat_id

    def get_files_rag(self, chat_id):
        """Return the cached RAG for this chat, if any."""
        return self.rag_cache.get(chat_id)

    def build_rag(self, file_path, file_ext, chat_id=None):
        # Each chat gets its own RAG instance/context
        rag = LangChainRAG(model="llama3-8b-8192")
        rag.build_index(file_path, file_type=file_ext)
        if chat_id:
            self.rag_cache[chat_id] = rag
        return rag

    def process_file(self, uploaded_file):
        """Save uploaded file and return its path and extension."""
        if not uploaded_file:
            return "", ""
        file_name = uploaded_file.name
        file_ext = uploaded_file.name.split('.')[-1].lower()
        save_dir = "uploaded_files"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file_name)
        with open(file_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        return file_path, file_ext

    def build_rag_from_text(self, text, chat_id=None):
        """
        Build a LangChainRAG index from a string (e.g., chat history).
        """
        temp_dir = "uploaded_files"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(
            temp_dir, f"temp_chat_history_{chat_id or 'global'}.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(text)
        rag = LangChainRAG(model="llama3-8b-8192")
        rag.build_index(temp_path, file_type="txt")
        if chat_id:
            self.rag_cache[chat_id] = rag
        return rag

    def enforce_token_limit(self, messages, max_tokens=6000):
        from langchain.prompts import PromptTemplate
        from langchain.prompts.example_selector import LengthBasedExampleSelector

        if not messages:
            return messages
        system_msg = messages[0]
        user_msg = messages[-1]
        examples = messages[1:-1]

        example_prompt = PromptTemplate(
            input_variables=["role", "content"],
            template="{role}: {content}"
        )

        selector = LengthBasedExampleSelector(
            examples=examples,
            example_prompt=example_prompt,
            max_length=max_tokens -
            self._count_tokens([system_msg, user_msg], example_prompt)
        )
        selected_examples = selector.select_examples({})

        trimmed = [system_msg] + selected_examples + [user_msg]
        return trimmed

    def _count_tokens(self, messages, prompt_template):
        total = 0
        for msg in messages:
            total += len(prompt_template.format(**msg).split())
        return total

    def get_completion(self, messages, query=None, files_rag=None, chat_history_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        # Fast path for new chats - bypass all RAG and token enforcement
        if is_new_chat:
            groq_client = Groq()
            # Ensure messages is a list of dicts, not a QuerySet or other complex object
            llm_messages = [{"role": msg['role'], "content": msg['content']} for msg in messages]
            completion = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024,
                stream=False,
            )
            return completion.choices[0].message.content
        
        # Regular code for existing chats...
        current_messages = [msg for msg in messages] # Make a mutable copy

        if not files_rag and chat_id: # Ensure files_rag is loaded if chat_id is available
            files_rag = self.get_files_rag(chat_id)

        context_str = ""
        retrieved_context = "" # Initialize to ensure it's always a string
        if files_rag and query:
            retrieved_context = files_rag.retrieve(query)
            self.logger.info(f"RAG retrieved_context for query '{query[:100]}...': '{str(retrieved_context)[:500]}...")
            if retrieved_context: # Check if anything was actually retrieved
                 context_str += str(retrieved_context) # Ensure it's a string
        
        # Placeholder for chat_history_rag if it were to be re-introduced and used similarly
        # if chat_history_rag and query:
        #     context_str += "\n" + chat_history_rag.retrieve(query)

        if context_str.strip():
            file_info = f" from the file '{attached_file_name}'" if attached_file_name else ""
            # If attached_file_name is None but files_rag was used, try to get a source from RAG
            if not file_info and files_rag and files_rag.chunks:
                try:
                    source_name = files_rag.chunks[0].metadata.get('source', 'the uploaded document')
                    file_info = f" from {source_name}"
                except (AttributeError, IndexError):
                    file_info = " from the uploaded document" # Fallback

            context_msg_content = (
                f"Relevant context has been retrieved{file_info}. "
                f"Use this information to answer the user's question or fulfill the request.\n\n"
                f"[BEGIN CONTEXT]\n{context_str}\n[END CONTEXT]"
            )
            context_message = {"role": "assistant", "content": context_msg_content}
            
            # Insert context message right before the last message (current user query/instruction)
            if current_messages:
                current_messages.insert(-1, context_message)
            else: # Should not happen if a query is present, but as a fallback
                current_messages.append(context_message)

        trimmed_messages = self.enforce_token_limit(current_messages, max_tokens=max_tokens)
        
        groq_client = Groq()
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_completion_tokens=1024,
            stream=False,
        )
        return completion.choices[0].message.content

    def stream_completion(self, messages, query=None, files_rag=None, chat_history_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        # Fast path for new chats - bypass all RAG and token enforcement
        if is_new_chat:
            groq_client = Groq()
            llm_messages = [{"role": msg['role'], "content": msg['content']} for msg in messages]
            return groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024,
                stream=True,
            )
        
        current_messages = [msg for msg in messages] # Make a mutable copy

        if not files_rag and chat_id: # Ensure files_rag is loaded if chat_id is available
            files_rag = self.get_files_rag(chat_id)

        context_str = ""
        retrieved_context = "" # Initialize
        if files_rag and query:
            retrieved_context = files_rag.retrieve(query)
            self.logger.info(f"RAG retrieved_context for query '{query[:100]}...': '{str(retrieved_context)[:500]}...")
            if retrieved_context: # Check if anything was actually retrieved
                 context_str += str(retrieved_context) # Ensure string
        
        # Placeholder for chat_history_rag logic
        # if chat_history_rag and query:
        #     context_str += "\n" + chat_history_rag.retrieve(query)
        
        if context_str.strip():
            file_info = f" from the file '{attached_file_name}'" if attached_file_name else ""
            if not file_info and files_rag and files_rag.chunks: # Try to get source from RAG metadata
                try:
                    source_name = files_rag.chunks[0].metadata.get('source', 'the uploaded document')
                    file_info = f" from {source_name}"
                except (AttributeError, IndexError):
                    file_info = " from the uploaded document"

            context_msg_content = (
                f"Relevant context has been retrieved{file_info}. "
                f"Use this information to answer the user's question or fulfill the request.\n\n"
                f"[BEGIN CONTEXT]\n{context_str}\n[END CONTEXT]"
            )
            context_message = {"role": "assistant", "content": context_msg_content}

            if current_messages:
                current_messages.insert(-1, context_message) # Insert before the last message
            else:
                current_messages.append(context_message)
        
        trimmed_messages = self.enforce_token_limit(current_messages, max_tokens=max_tokens)
        groq_client = Groq()
        return groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_completion_tokens=1024,
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
