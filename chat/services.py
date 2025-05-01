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
        # Use PDFMiner for PDFs, TextLoader for txt
        if file_type == "pdf":
            # Extract text from PDF using pdfminer
            text = extract_text(file_path)
            temp_txt_path = file_path + ".txt"
            with open(temp_txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            # <-- specify encoding!
            loader = TextLoader(temp_txt_path, encoding="utf-8")
        else:
            # <-- specify encoding!
            loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        self.chunks = splitter.split_documents(docs)
        # Embedding and vectorstore
        embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name)
        self.vectorstore = FAISS.from_documents(self.chunks, embeddings)
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
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

    def get_completion(self, messages, query=None, files_rag=None, chat_history_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False):
        # Always use cached file RAG if available and not a new chat
        if not files_rag and chat_id and not is_new_chat:
            files_rag = self.get_files_rag(chat_id)
        context = ""
        if not is_new_chat:
            if files_rag and query:
                context += files_rag.retrieve(query)
            if chat_history_rag and query:
                context += "\n" + chat_history_rag.retrieve(query)
        if context.strip():
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    context_msg = {
                        "role": "system",
                        "content": f"Relevant context:\n\n{context}\n\nUse this information to answer the user's query."
                    }
                    messages.insert(i+1, context_msg)
                    break
        trimmed_messages = self.enforce_token_limit(
            messages, max_tokens=max_tokens)
        groq_client = Groq()
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_completion_tokens=1024,
            stream=False,
        )
        return completion.choices[0].message.content

    def stream_completion(self, messages, query=None, files_rag=None, chat_history_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False):
        # Always use cached file RAG if available and not a new chat
        if not files_rag and chat_id and not is_new_chat:
            files_rag = self.get_files_rag(chat_id)
        context = ""
        if not is_new_chat:
            if files_rag and query:
                context += files_rag.retrieve(query)
            if chat_history_rag and query:
                context += "\n" + chat_history_rag.retrieve(query)
        if context.strip():
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    context_msg = {
                        "role": "system",
                        "content": f"Relevant context:\n\n{context}\n\nUse this information to answer the user's query."
                    }
                    messages.insert(i+1, context_msg)
                    break
        trimmed_messages = self.enforce_token_limit(
            messages, max_tokens=max_tokens)
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
                f'chat_uploads/{chat_id}/{uploaded_file.name}',
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
