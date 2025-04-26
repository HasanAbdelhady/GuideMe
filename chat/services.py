import os
import datetime
from .models import Message
from .ai_models import AIModelManager
from .preference_service import PreferenceService
from django.core.files.storage import default_storage
from pdfminer.layout import LAParams
from io import StringIO
import logging
import re
from pdfminer.high_level import extract_text_to_fp
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import tiktoken
import copy

class RAG:
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(embedding_model_name)
        self.index = None
        self.chunks = []

    def chunk_text(self, text, chunk_size=1000, overlap=200):
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i+chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def build_index(self, text):
        self.chunks = self.chunk_text(text)
        embeddings = self.model.encode(self.chunks)
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(np.array(embeddings).astype('float32'))

    def retrieve(self, query, top_k=5):
        query_emb = self.model.encode([query])
        D, I = self.index.search(np.array(query_emb).astype('float32'), top_k)
        return [self.chunks[i] for i in I[0]]

def count_tokens(messages, encoding):
    total = 0
    for msg in messages:
        total += len(encoding.encode(msg.get("role", "")))
        total += len(encoding.encode(msg.get("content", "")))
    return total

class ChatService:
    def __init__(self):
        self.ai_manager = AIModelManager()
        self.logger = logging.getLogger(__name__)
        self.rag = RAG()

    def extract_pdf_content(self, pdf_file):
        """Extract text from PDF using PDFMiner.six with optimized parameters."""
        output = StringIO()
        laparams = LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5,
            detect_vertical=True
        )
        try:
            extract_text_to_fp(pdf_file, output, laparams=laparams)
            return output.getvalue()
        except Exception as e:
            self.logger.error(f"PDF extraction error: {e}")
            raise
        finally:
            output.close()

    def process_text_content(self, content):
        """Process and clean extracted text content."""
        parts = re.split(r'\bREFERENCES\b', content, flags=re.IGNORECASE, maxsplit=1)
        text = parts[0].strip()
        cleaning_rules = [
            (r'(\w+)-\s*\n\s*(\w+)', r'\1\2'),
            (r'(\w+)\s+(\w)\n', r'\1\2\n'),
            (r'\s+([.,;:)!?])', r'\1'),
            (r'([A-Z])\s+([A-Z][A-Z])', r'\1\2'),
            (r'\s{2,}', ' '),
            (r'\n{3,}', '\n\n')
        ]
        for pattern, replacement in cleaning_rules:
            text = re.sub(pattern, replacement, text)
        return text.strip()

    def process_file(self, uploaded_file):
        """Process uploaded file and extract its content."""
        if not uploaded_file:
            return "", ""
        file_name = uploaded_file.name
        file_ext = uploaded_file.name.split('.')[-1].lower()
        try:
            if file_ext == 'pdf':
                content = self.extract_pdf_content(uploaded_file)
                file_content = self.process_text_content(content)
            else:
                file_content = uploaded_file.read().decode('utf-8', errors='replace')
                uploaded_file.seek(0)
                file_content = self.process_text_content(file_content)

            self.rag.build_index(file_content)

            # Save processed text and chunks for debugging/auditing
            save_dir = "processed_outputs"
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(file_name)[0]
            processed_path = os.path.join(save_dir, f"{base_name}_processed_{timestamp}.txt")
            with open(processed_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"Processed PDF text saved to: {processed_path}")

            chunks_path = os.path.join(save_dir, f"{base_name}_chunks_{timestamp}.txt")
            with open(chunks_path, "w", encoding="utf-8") as f:
                for chunk in self.rag.chunks:
                    f.write(chunk + "\n\n")
            print(f"Chunked text for embeddings saved to: {chunks_path}")

            return file_name, file_content
        except Exception as e:
            self.logger.error(f"File processing error: {str(e)}")
            raise Exception(f"Error processing file: {str(e)}")

    def get_relevant_context(self, query, max_tokens=6000, reply_buffer=800, messages=None, rag=None):
        encoding = tiktoken.get_encoding("cl100k_base")
        rag_instance = rag if rag is not None else self.rag
        chunks = rag_instance.retrieve(query, top_k=50)
        context = []
        total_tokens = 0
        used_tokens = count_tokens(messages or [], encoding)
        context_limit = max_tokens - reply_buffer - used_tokens
        if context_limit <= 0:
            return ""
        for chunk in chunks:
            chunk_tokens = len(encoding.encode(chunk))
            if total_tokens + chunk_tokens > context_limit:
                break
            context.append(chunk)
            total_tokens += chunk_tokens
        return "\n".join(context)

    def get_completion(self, messages, query=None, max_tokens=5000, rag=None):
        if query:
            context = self.get_relevant_context(query, max_tokens=max_tokens, messages=messages, rag=rag)
            messages.append({"role": "system", "content": f"Relevant context:\n{context}"})

        trimmed = trim_messages_to_token_limit(messages, max_tokens)

        # --- Save the final context/messages passed to the LLM ---
        save_dir = "processed_outputs"
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        context_path = os.path.join(save_dir, f"context_for_llm_{timestamp}.txt")
        with open(context_path, "w", encoding="utf-8") as f:
            for msg in trimmed:
                f.write(f"{msg['role'].upper()}:\n{msg['content']}\n\n{'-'*40}\n\n")
        print(f"Context passed to LLM saved to: {context_path}")

        return self.ai_manager.get_chat_completion(trimmed)

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

    def get_chat_history(self, chat, limit=10):
        return list(chat.messages.all().order_by('created_at'))[-limit:]

    def update_chat_title(self, chat, title_text=None):
        if not title_text:
            return
        chat.title = title_text[:50] + ('...' if len(title_text) > 50 else '')
        chat.save()

    def create_rag_instance(self):
        return RAG()

def trim_messages_to_token_limit(messages, max_tokens=5000):
    encoding = tiktoken.get_encoding("cl100k_base")
    trimmed = copy.deepcopy(messages)
    # Always keep the system prompt (first message)
    system_msg = trimmed[0] if trimmed and trimmed[0]["role"] == "system" else None
    # Always keep the last user message
    last_user_msg = None
    for msg in reversed(trimmed):
        if msg["role"] == "user":
            last_user_msg = msg
            break

    # Start with system and last user message
    base = [system_msg] if system_msg else []
    if last_user_msg and last_user_msg is not system_msg:
        base.append(last_user_msg)

    # Add messages from the end backwards (excluding system and last user)
    idx = len(trimmed) - 1
    while idx >= 0:
        msg = trimmed[idx]
        if msg is system_msg or msg is last_user_msg:
            idx -= 1
            continue
        base.insert(-1 if last_user_msg else len(base), msg)
        if count_tokens(base, encoding) > max_tokens:
            base.pop(-1 if last_user_msg else len(base)-1)
            break
        idx -= 1

    # If still too long, truncate the last message's content
    while count_tokens(base, encoding) > max_tokens and len(base) > 0:
        last_msg = base[-1]
        content = last_msg.get("content", "")
        allowed = max_tokens - (count_tokens(base[:-1], encoding) + len(encoding.encode(last_msg.get("role", ""))))
        if allowed > 0:
            last_msg["content"] = encoding.decode(encoding.encode(content)[:allowed])
        else:
            base.pop(-1)
    return base
