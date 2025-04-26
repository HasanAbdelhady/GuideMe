import os
import datetime
import json
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
from functools import lru_cache

class RAG:
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(embedding_model_name)
        self.index = None
        self.chunks = []
        self.metadata = []
        self.relevance_threshold = 0.5
        self.file_identifier = None

    def chunk_text(self, text, chunk_size=1000, overlap=200):
        """Chunk text using a more semantic approach with paragraph awareness"""
        # First split by paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        chunk_metadata = []
        current_chunk = ""
        current_metadata = {"paragraphs": []}
        
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
                
            # If adding this paragraph would exceed chunk size, start a new chunk
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                chunk_metadata.append(current_metadata)
                current_chunk = para
                current_metadata = {"paragraphs": [i]}
            else:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += para
                current_metadata["paragraphs"].append(i)
                
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk.strip())
            chunk_metadata.append(current_metadata)
            
        # If chunks are too small, merge them
        if len(chunks) > 1:
            merged_chunks = []
            merged_metadata = []
            current_chunk = chunks[0]
            current_metadata = chunk_metadata[0]
            
            for i in range(1, len(chunks)):
                if len(current_chunk) + len(chunks[i]) <= chunk_size:
                    current_chunk += "\n\n" + chunks[i]
                    current_metadata["paragraphs"].extend(chunk_metadata[i]["paragraphs"])
                else:
                    merged_chunks.append(current_chunk)
                    merged_metadata.append(current_metadata)
                    current_chunk = chunks[i]
                    current_metadata = chunk_metadata[i]
                    
            merged_chunks.append(current_chunk)
            merged_metadata.append(current_metadata)
            
            return merged_chunks, merged_metadata
        
        return chunks, chunk_metadata

    def build_index(self, text, file_identifier=None):
        """Build FAISS index from text content with improved chunking"""
        self.file_identifier = file_identifier
        self.chunks, self.metadata = self.chunk_text(text)
        
        # Store chunk sources in metadata
        for i, meta in enumerate(self.metadata):
            meta["index"] = i
            meta["source"] = file_identifier if file_identifier else "chat_history"
            meta["chunk_text"] = self.chunks[i][:100] + "..."  # Preview for debugging
        
        # Compute embeddings for all chunks
        embeddings = self.model.encode(self.chunks)
        
        # Create and populate FAISS index
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(np.array(embeddings).astype('float32'))

    def retrieve(self, query, top_k=10, min_score=0.7):
        """Retrieve relevant chunks with scores and apply reranking"""
        if not self.index or not self.chunks:
            return []
            
        # Encode query and search
        query_emb = self.model.encode([query])
        D, I = self.index.search(np.array(query_emb).astype('float32'), min(top_k, len(self.chunks)))
        
        # Convert distances to similarity scores (higher is better)
        max_distance = np.max(D) if len(D) > 0 and len(D[0]) > 0 else 1.0
        similarity_scores = [1.0 - (d / max_distance) for d in D[0]]
        
        # Get chunks with their scores and metadata
        results = []
        for i, (idx, score) in enumerate(zip(I[0], similarity_scores)):
            if idx < len(self.chunks) and score >= min_score:
                results.append({
                    "text": self.chunks[idx],
                    "score": score,
                    "metadata": self.metadata[idx] if idx < len(self.metadata) else {}
                })
        
        # Simple reranking: Boost longer chunks slightly and chunks with exact query terms
        for result in results:
            # Adjust score based on length (slightly favor longer chunks)
            length_factor = min(len(result["text"]) / 2000, 1.0) * 0.1
            
            # Adjust score based on lexical match
            query_terms = set(re.findall(r'\b\w+\b', query.lower()))
            chunk_terms = set(re.findall(r'\b\w+\b', result["text"].lower()))
            term_overlap = len(query_terms.intersection(chunk_terms)) / max(len(query_terms), 1)
            term_factor = term_overlap * 0.2
            
            # Apply the adjustments
            result["score"] = min(result["score"] + length_factor + term_factor, 1.0)
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]

@lru_cache(maxsize=10)
def get_encoding():
    """Cached function to get tokenizer encoding"""
    return tiktoken.get_encoding("cl100k_base")

def count_tokens(messages, encoding=None):
    """Count tokens in messages with caching"""
    if encoding is None:
        encoding = get_encoding()
    total = 0
    for msg in messages:
        total += len(encoding.encode(msg.get("role", "")))
        total += len(encoding.encode(msg.get("content", "")))
    return total

class ChatService:
    def __init__(self):
        self.ai_manager = AIModelManager()
        self.logger = logging.getLogger(__name__)
        self.rag_cache = {}  # Cache RAG instances by file_id

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
        file_id = f"{file_name}_{hash(file_name)}"
        print(f"ext {file_ext}")
        print(f"id {file_id}")
        try:
            # Check if we already have this file processed in cache
            if file_id in self.rag_cache:
                print("id in cache")
                self.logger.info(f"Using cached RAG instance for {file_name}")
                return file_name, self.rag_cache[file_id]  # Return the cached content
                
            if file_ext == 'pdf':
                content = self.extract_pdf_content(uploaded_file)
                file_content = self.process_text_content(content)
            else:
                file_content = uploaded_file.read().decode('utf-8', errors='replace')
                uploaded_file.seek(0)
                file_content = self.process_text_content(file_content)

            # Save processed text and chunks for debugging/auditing
            save_dir = "processed_outputs"
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(file_name)[0]
            processed_path = os.path.join(save_dir, f"{base_name}_processed_{timestamp}.txt")
            with open(processed_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            self.logger.info(f"Processed file text saved to: {processed_path}")

            # Cache the processed content
            self.rag_cache[file_id] = file_content
            
            return file_name, file_content  # Return the actual content
        except Exception as e:
            self.logger.error(f"File processing error: {str(e)}")
            raise Exception(f"Error processing file: {str(e)}")

    def get_relevant_context(self, query, files_rag=None, chat_history_rag=None, max_tokens=6000, reply_buffer=800, messages=None):
        """Get combined context from files and chat history"""
        encoding = get_encoding()
        used_tokens = count_tokens(messages or [], encoding)
        context_limit = max_tokens - reply_buffer - used_tokens
        
        if context_limit <= 0:
            return ""
            
        all_results = []
        
        # Get results from files if available
        if files_rag and files_rag.index:
            file_results = files_rag.retrieve(query, top_k=15, min_score=0.65)
            for result in file_results:
                result["source"] = "file"
            all_results.extend(file_results)
            
        # Get results from chat history if available
        if chat_history_rag and chat_history_rag.index:
            history_results = chat_history_rag.retrieve(query, top_k=10, min_score=0.7)
            for result in history_results:
                result["source"] = "history"
            all_results.extend(history_results)
            
        # Sort all results by score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Deduplicate results - remove highly similar chunks
        deduplicated = []
        seen_content = set()
        
        for result in all_results:
            # Create a simplified representation for deduplication
            content_hash = hash(re.sub(r'\s+', ' ', result["text"]).lower())
            if content_hash not in seen_content:
                deduplicated.append(result)
                seen_content.add(content_hash)
        
        # Format and combine the results within token limit
        context_chunks = []
        total_tokens = 0
        
        for result in deduplicated:
            chunk_text = result["text"]
            chunk_tokens = len(encoding.encode(chunk_text))
            source_info = f"[Source: {result['source']}, Relevance: {result['score']:.2f}]"
            
            if total_tokens + chunk_tokens + len(encoding.encode(source_info)) > context_limit:
                break
                
            context_chunks.append(f"{source_info}\n{chunk_text}")
            total_tokens += chunk_tokens + len(encoding.encode(source_info))
        
        return "\n\n---\n\n".join(context_chunks)

    def get_completion(self, messages, query=None, max_tokens=5000, files_rag=None, chat_history_rag=None):
        combined_context = ""
        if query:
            combined_context = self.get_relevant_context(
                query, 
                files_rag=files_rag, 
                chat_history_rag=chat_history_rag,
                max_tokens=max_tokens,
                messages=messages
            )
        # Fallback: if combined_context is empty but files_rag exists, add first chunk(s)
        if not combined_context and files_rag and files_rag.chunks:
            fallback_chunks = files_rag.chunks[:2]
            combined_context = "\n\n".join(fallback_chunks)
        if combined_context:
            # Insert the context after the system message
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    context_msg = {
                        "role": "system", 
                        "content": f"Below is relevant context from files and chat history that may help you answer the user's query.\n\n{combined_context}\n\nUse this information to provide a comprehensive and accurate answer. Only reference this context if relevant to the user's query."
                    }
                    messages.insert(i+1, context_msg)
                    break

        trimmed = trim_messages_to_token_limit(messages, max_tokens)

        # Save the final context/messages passed to the LLM
        save_dir = "processed_outputs"
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        context_path = os.path.join(save_dir, f"context_for_llm_{timestamp}.txt")
        with open(context_path, "w", encoding="utf-8") as f:
            for msg in trimmed:
                f.write(f"{msg['role'].upper()}:\n{msg['content']}\n\n{'-'*40}\n\n")
        self.logger.info(f"Context passed to LLM saved to: {context_path}")

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

    def get_chat_history(self, chat, limit=20):
        return list(chat.messages.all().order_by('created_at'))[-limit:]

    def update_chat_title(self, chat, title_text=None):
        if not title_text:
            return
        chat.title = title_text[:50] + ('...' if len(title_text) > 50 else '')
        chat.save()

    def create_rag_instance(self, file_identifier=None):
        """Create a new RAG instance with optional identifier"""
        rag = RAG()
        if file_identifier:
            rag.file_identifier = file_identifier
        return rag

def trim_messages_to_token_limit(messages, max_tokens=5000):
    """Trim messages to fit within token limit while preserving important messages"""
    encoding = get_encoding()
    trimmed = copy.deepcopy(messages)
    
    # Always keep system messages
    system_msgs = [msg for msg in trimmed if msg["role"] == "system"]
    # Always keep the last user message
    last_user_msg = None
    for msg in reversed(trimmed):
        if msg["role"] == "user":
            last_user_msg = msg
            break

    # Start with system messages and last user message
    base = system_msgs.copy()
    if last_user_msg and last_user_msg not in system_msgs:
        base.append(last_user_msg)

    # Add back-and-forth conversation history, prioritizing recent messages
    remaining_msgs = [msg for msg in trimmed if msg not in system_msgs and msg is not last_user_msg]
    remaining_msgs.reverse()  # Start from most recent
    
    for msg in remaining_msgs:
        test_base = base.copy()
        # Try to insert before the last user message if it exists
        insert_idx = len(base) if last_user_msg is None else base.index(last_user_msg)
        test_base.insert(insert_idx, msg)
        if count_tokens(test_base, encoding) <= max_tokens:
            base.insert(insert_idx, msg)
        else:
            break

    # If still too long, truncate the system messages' content (preserving the first one)
    if count_tokens(base, encoding) > max_tokens and len(base) > 1:
        first_system = next((msg for msg in base if msg["role"] == "system"), None)
        system_to_truncate = [msg for msg in base if msg["role"] == "system" and msg is not first_system]
        
        for msg in system_to_truncate:
            if count_tokens(base, encoding) <= max_tokens:
                break
            content = msg.get("content", "")
            allowed = max_tokens - (count_tokens([m for m in base if m is not msg], encoding) + 
                                    len(encoding.encode(msg.get("role", ""))))
            if allowed > 100:  # Only truncate if we can keep a meaningful amount
                msg["content"] = encoding.decode(encoding.encode(content)[:allowed])
            else:
                base.remove(msg)
    
    # If still too long as a last resort, truncate the first system message
    if count_tokens(base, encoding) > max_tokens and len(base) > 0:
        first_system = next((msg for msg in base if msg["role"] == "system"), None)
        if first_system:
            content = first_system.get("content", "")
            allowed = max_tokens - (count_tokens([m for m in base if m is not first_system], encoding) + 
                                   len(encoding.encode(first_system.get("role", ""))))
            if allowed > 200:  # Preserve at least 200 tokens of system instruction
                first_system["content"] = encoding.decode(encoding.encode(content)[:allowed])
    
    return base