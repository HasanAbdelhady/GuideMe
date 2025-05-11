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
import time
# import base64 # No longer needed if generate_mindmap_image_data_url is removed
import asyncio
from asgiref.sync import sync_to_async

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

import graphviz # Added for diagram generation
import re # Added for sanitizing filenames


def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

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

    async def get_completion(self, messages, query=None, files_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        groq_client_local = Groq() # Keep client instantiation local if it has state issues with async
        
        if is_new_chat:
            llm_messages = [{'role': msg['role'], 'content': msg['content']} for msg in messages]
            # This part should be sync or wrapped if get_completion is to be truly async.
            # For now, assuming it's called in a context that can handle this if it blocks briefly,
            # or that this path is less critical for full async behavior if it's just for the first message.
            completion = (groq_client_local.chat.completions.create)(
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024,
                stream=False,
            )
            return completion.choices[0].message.content
        
        current_messages_copy = [msg.copy() for msg in messages] # Work with a copy

        context_str = ""
        rag_output = ""
        if files_rag and query:
            # Assuming files_rag.retrieve is CPU bound or already async; if sync I/O, wrap it
            # For now, let's assume it's okay or needs to be made async separately if it blocks.
            # retrieved_context_val = await sync_to_async(files_rag.retrieve)(query) # Example if it needed wrapping
            retrieved_context_val = files_rag.retrieve(query) # Original
            rag_output = retrieved_context_val
            self.logger.info(f"RAG output HERE!!!!!!!!!!! {str(rag_output)[:500]}...")
            if retrieved_context_val:
                 context_str += str(retrieved_context_val)
        
        if context_str.strip():
            rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"
            if current_messages_copy and current_messages_copy[-1]["role"] == "user":
                original_user_content = current_messages_copy[-1]["content"]
                context_preamble = f"Relevant context from your uploaded documents ({rag_info_source}):\n\"\"\"{context_str}\"\"\"\n---\nOriginal query follows:\n"
                current_messages_copy[-1]["content"] = context_preamble + original_user_content
            else:
                self.logger.warning("Could not find user message to prepend RAG context to.")

        trimmed_messages = self.enforce_token_limit(current_messages_copy, max_tokens=max_tokens)
        
        # Wrap the synchronous SDK call
        completion = await sync_to_async(groq_client_local.chat.completions.create)(
            model="llama3-8b-8192",
            messages=trimmed_messages,
            temperature=0.7,
            max_completion_tokens=1024,
            stream=False,
        )
        # Logic for RAG output vs LLM completion seems to have an issue here.
        # If rag_output exists, it should likely be returned, not the LLM completion directly unless RAG modifies the query for LLM.
        # This part of the logic needs review from original implementation if RAG output should take precedence.
        # For now, mimicking the original structure but noting this potential issue.
        if rag_output: # This was the original logic, implies rag_output is preferred IF it exists
            self.logger.info(f"In rag_output - returning RAG output directly.")
            return rag_output 
        else:
            self.logger.info(f"No RAG output, returning LLM completion.")
            return completion.choices[0].message.content

    async def stream_completion(self, messages, query=None, files_rag=None, max_tokens=6000, chat_id=None, is_new_chat=False, attached_file_name=None):
        groq_client_local = Groq() # Keep client instantiation local

        if is_new_chat:
            llm_messages = [{'role': msg['role'], 'content': msg['content']} for msg in messages]
            # Wrap the synchronous SDK call for streaming
            # sync_to_async might not work as expected with generators/iterators returned by stream=True.
            # The Groq SDK would ideally offer an async client for streaming.
            # If not, this is a more complex case. A common pattern is to run the sync streaming call in a separate thread.
            # For now, let's assume this was intended to be a blocking call in the view if is_new_chat was handled differently, 
            # or the view needs to adapt how it consumes this if it's a sync generator.
            # Given the current view structure expects an async generator, this is problematic.
            #
            # **Simplification for now: If is_new_chat, use get_completion and simulate stream in view, or make get_completion stream-like.**
            # **For the purpose of this fix, let's assume stream=True with sync_to_async is problematic and needs a different approach for true async streaming.**
            # **However, the view calls this and then iterates. The issue in the view was sync DB calls, not necessarily this call if the view handles its sync nature.**
            # **Let's revert to calling it as it was, assuming the caller (sync_wrapper_for_event_stream) handles its sync generator nature.**
            # The original error was SynchronousOnlyOperation from ORM calls, not directly from here.
            return groq_client_local.chat.completions.create( # Keeping this sync as it returns a generator
                model="llama3-8b-8192",
                messages=llm_messages,
                temperature=0.7,
                max_completion_tokens=1024,
                stream=True,
            )

        current_messages_copy = [msg.copy() for msg in messages] # Work with a copy
        context_str = ""
        raggyy = "" # Original name from user's code was raggyy

        if files_rag and query:
            # retrieved_context_val = await sync_to_async(files_rag.retrieve)(query) # Example if needed
            retrieved_context_val = files_rag.retrieve(query) # Original
            raggyy = retrieved_context_val
            if retrieved_context_val:
                 context_str += str(retrieved_context_val)
        
        if context_str.strip():
            rag_info_source = f" from {attached_file_name}" if attached_file_name else " from uploaded RAG documents"
            if current_messages_copy and current_messages_copy[-1]["role"] == "user":
                original_user_content = current_messages_copy[-1]["content"]
                context_preamble = f"Relevant context from your uploaded documents ({rag_info_source}):\n\"\"\"{context_str}\"\"\"\n---\nOriginal query follows:\n"
                current_messages_copy[-1]["content"] = context_preamble + original_user_content
            else:
                self.logger.warning("Could not find user message to prepend RAG context in stream_completion.")

        trimmed_messages = self.enforce_token_limit(current_messages_copy, max_tokens=max_tokens)
        
        # This logic for raggyy returning early seems to bypass LLM streaming. Review if this is intended.
        if raggyy: # If RAG produced direct output, return it (not a stream)
            self.logger.info(f"Returning direct RAG output (raggyy) in stream_completion context.")
            return raggyy 
        else:
            # This returns a synchronous generator from the Groq SDK
            return groq_client_local.chat.completions.create(
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

    async def generate_diagram_image(self, chat_history_messages, user_query, chat_id, user_id):
        self.logger.info(f"Starting diagram generation for chat {chat_id}, user query: {user_query}")
        prompt_content_generation = (
            'You are an expert explainer working in a multi-agent system.\\n'
            'Your job is to generate a clear, structured, and technically accurate description of a given topic so it can be turned into a diagram.\\n'
            'Requirements:\\n'
            '- Break down the topic into logical steps, layers, or components.\\n'
            '- Describe each part in order of how it flows or interacts with others.\\n'
            '- Focus on function, purpose, input/output, and relationships.\\n'
            '- Keep the explanation concise but informative — not too short, not too long.\\n'
            '- The description should be suitable for transforming into a technical diagram using Graphviz.\\n'
            'Your output must be plain text, without code or special formatting.'
        )
        
        messages_for_description = chat_history_messages + [{"role": "user", "content": user_query}]
        messages_for_description.insert(0, {"role": "system", "content": prompt_content_generation})
        self.logger.info(f"Messages for description LLM call (first few): {str(messages_for_description)[:200]}")

        try:
            structured_description_content = await self.get_completion(
                messages=messages_for_description,
                max_tokens=1500, 
                chat_id=chat_id 
            )
            self.logger.info(f"Received structured description: {structured_description_content[:200]}...")
            if not structured_description_content or not structured_description_content.strip():
                self.logger.error("LLM failed to generate a structured description.")
                return None
        except Exception as e:
            self.logger.error(f"Error getting structured description from LLM: {e}", exc_info=True)
            return None

        # Simplified prompt for Graphviz code generation
        prompt_graphviz_code_generation = (
            "You are an expert technical diagram assistant. Your task is to generate ONLY Python code using the Graphviz library "
            "to create an educational diagram based on the provided structured description.\\n\\n"
            "IMPORTANT: Return ONLY the exact Python code with no explanations, no markdown formatting, no ```python blocks, and no comments outside the code. "
            "Start your response directly with 'from graphviz import Digraph' or the appropriate import statement.\\n\\n"
            "The Python script should:\\n"
            "- Import `Digraph` from `graphviz` (e.g., `from graphviz import Digraph`).\\n"
            "- Create a `Digraph` object with ONLY the format parameter: `g = Digraph(format='png')`.\\n"
            "- Set other graph attributes using the `.attr()` method AFTER creation: `g.attr(dpi='300')` and `g.attr(rankdir='TB')`.\\n"
            "- Define nodes using `g.node(node_id, label, shape='box', style='filled,rounded', fillcolor='color')`. Do NOT use invalid attributes like 'parent'.\\n"
            "- Define edges using `g.edge(parent_id, child_id, label=optional_label)`. ALWAYS ensure all parentheses are properly closed.\\n"
            "- EXAMPLE of a correct edge definition: `g.edge(\"node1\", \"node2\", label=\"connects to\")` - note the closing parenthesis.\\n"
            "- Create hierarchical relationships by explicitly creating edges between nodes, not by adding nodes with 'parent' attributes.\\n"
            "- For mind maps specifically, use a central node and connect all main concepts to it.\\n"
            "- Optionally, use subgraphs/clusters for logical grouping.\\n"
            "- Optionally, include educational annotations as separate nodes.\\n"
            "- CAREFULLY check your code for syntax errors, especially unclosed parentheses in method calls.\\n"
            "- Always conclude with `g.render('diagram_output', view=False, cleanup=True)` to generate the diagram.\\n\\n"
        )
        
        messages_for_graphviz = [
            {"role": "system", "content": prompt_graphviz_code_generation},
            {"role": "user", "content": structured_description_content} # The LLM-generated description
        ]
        self.logger.info(f"Messages for Graphviz LLM call (system prompt length: {len(prompt_graphviz_code_generation)}, user content length: {len(structured_description_content) if structured_description_content else 0})")

        try:
            graphviz_code_response = await self.get_completion(
                messages=messages_for_graphviz,
                max_tokens=2500, # Allow ample tokens for code generation
                chat_id=chat_id
            )
            self.logger.info(f"Received Graphviz code response (first 200 chars): {graphviz_code_response[:200] if graphviz_code_response else 'Empty response'}...")
            if not graphviz_code_response or not graphviz_code_response.strip():
                self.logger.error("LLM failed to generate Graphviz code (empty response).")
                return None
        except Exception as e:
            self.logger.error(f"Error getting Graphviz code from LLM: {e}", exc_info=True)
            return None

        # Since the prompt now asks for ONLY Python code, no ```python ``` block is expected.
        # We'll take the response as is, after stripping whitespace.
        graphviz_code = graphviz_code_response.strip()
        
        # Extract only the actual Python code, removing any explanatory text
        if "```" in graphviz_code:
            # If the response has code blocks, extract the content between the first set of ``` markers
            try:
                code_parts = graphviz_code.split("```")
                if len(code_parts) >= 3:  # At least one complete code block
                    graphviz_code = code_parts[1].strip()
                    # If it starts with 'python', remove that too
                    if graphviz_code.startswith("python"):
                        graphviz_code = graphviz_code[6:].strip()
            except Exception as e:
                self.logger.error(f"Error extracting code block: {e}", exc_info=True)
        else:
            # If no code blocks, try to find the first line that looks like Python code
            lines = graphviz_code.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("from") or line.strip().startswith("import") or "Digraph" in line:
                    start_idx = i
                    break
            graphviz_code = "\n".join(lines[start_idx:])
        
        self.logger.info(f"Cleaned Graphviz code (first 100 chars): {graphviz_code[:100]}...")
        
        # More lenient check - only require import and Digraph creation
        if not ("from graphviz import Digraph" in graphviz_code and "Digraph(" in graphviz_code):
            self.logger.error(f"Generated Graphviz code does not appear to be valid. Preview: {graphviz_code[:500]}")
            return None
            
        # Add fallback .render() call if missing
        if ".render(" not in graphviz_code:
            self.logger.info("Adding fallback .render() call to Graphviz code")
            # Add render call to the end of the code
            graphviz_code += "\n\n# Fallback render call\ng.render('diagram_output', view=False, cleanup=True)"
            
        # Pre-process the code to handle common issues
        # Remove invalid 'parent' attribute which is a common mistake in the generated code
        graphviz_code = re.sub(r'parent\s*=\s*[\'"].*?[\'"]', '', graphviz_code)
        self.logger.info(f"Pre-processed Graphviz code (first 300 chars): {graphviz_code[:300]}...")

        # Add syntax validation and correction for common issues
        def validate_and_fix_syntax(code):
            # Check for and fix unclosed parentheses in edge definitions
            fixed_code = []
            in_edge_def = False
            paren_count = 0
            
            for line in code.split('\n'):
                if 'g.edge(' in line:
                    # Count opening and closing parentheses
                    open_count = line.count('(')
                    close_count = line.count(')')
                    
                    if open_count > close_count:
                        # Unclosed parenthesis - add missing closing parenthesis
                        self.logger.info(f"Fixing unclosed parenthesis in edge definition: {line}")
                        line = line + ')' * (open_count - close_count)
                
                fixed_code.append(line)
            
            return '\n'.join(fixed_code)
            
        # Apply syntax fixes
        graphviz_code = validate_and_fix_syntax(graphviz_code)
        self.logger.info("Applied syntax validation and fixes to Graphviz code")

        def _render_graphviz_sync(code_to_execute, base_filename, topic_name_from_query):
            # Simplify path structure to match actual storage location
            diagram_dir = os.path.join('media', 'diagrams')
            os.makedirs(diagram_dir, exist_ok=True)
            
            # Create a more standardized filename
            safe_topic = sanitize_filename(topic_name_from_query).replace(' ', '_')
            timestamp = int(time.time())
            filename = f"{base_filename}_{safe_topic}_{timestamp}.png"
            output_filepath = os.path.join(diagram_dir, filename)
            
            # Get absolute paths for clarity in logging
            abs_diagram_dir = os.path.abspath(diagram_dir)
            abs_output_filepath = os.path.abspath(output_filepath)
            self.logger.info(f"Diagram directory (absolute): {abs_diagram_dir}")
            self.logger.info(f"Output filepath (absolute): {abs_output_filepath}")
            
            # For the URL, we'll return just the path relative to media directory
            relative_url_path = f"diagrams/{filename}"

            try:
                # First validate code syntax before executing
                import ast
                try:
                    ast.parse(code_to_execute)
                    self.logger.info("Code syntax validation passed")
                except SyntaxError as se:
                    self.logger.error(f"Syntax error in generated code: {se}")
                    # Try simple syntax fixes for common errors
                    line_number = se.lineno if hasattr(se, 'lineno') else -1
                    if line_number > 0:
                        lines = code_to_execute.split('\n')
                        if line_number <= len(lines):
                            problematic_line = lines[line_number - 1]
                            self.logger.error(f"Problematic line ({line_number}): {problematic_line}")
                            # Try to fix specific syntax issues like unclosed parentheses
                            if '(' in problematic_line and ')' not in problematic_line:
                                lines[line_number - 1] = problematic_line + ')'
                                self.logger.info(f"Attempted to fix unclosed parenthesis: {lines[line_number - 1]}")
                                code_to_execute = '\n'.join(lines)
                                try:
                                    ast.parse(code_to_execute)
                                    self.logger.info("Code syntax fixed and now valid")
                                except SyntaxError:
                                    self.logger.error("Failed to fix syntax error")
                
                # Log the cleaned code for debugging
                self.logger.info(f"About to execute graphviz code:\n---CODE START---\n{code_to_execute}\n---CODE END---")
                
                local_namespace = {}
                # Provide necessary imports to the execution scope
                exec_globals = {"graphviz": graphviz, "Digraph": graphviz.Digraph, "os": os}
                exec(code_to_execute, exec_globals, local_namespace)
                
                # The LLM should have created a Digraph object, commonly 'g'
                # and called g.render(). We will try to find the path it rendered to,
                # or use our standard path if the LLM's .render() call was generic.
                
                graph_object_name = None
                for name, val in local_namespace.items():
                    if isinstance(val, graphviz.Digraph):
                        graph_object_name = name
                        self.logger.info(f"Found graph object: {name}")
                        break
                
                if graph_object_name:
                    graph_obj = local_namespace[graph_object_name]
                    # Ensure our desired output settings are applied if possible,
                    # though the prompt asks the LLM to set them.
                    graph_obj.format = 'png'
                    
                    # The LLM was instructed to call .render().
                    # If it used a generic name like 'diagram_output', our output_filepath_stem will be used.
                    # If it created a file, we need to find it.
                    # For robust_ness, we will call render again with our explicit path.
                    # This ensures the file is where we expect it.
                    filepath_without_ext = os.path.splitext(output_filepath)[0]  # Remove .png extension for render
                    self.logger.info(f"About to render graph to {filepath_without_ext}")
                    rendered_path = graph_obj.render(filename=filepath_without_ext, view=False, cleanup=True)
                    self.logger.info(f"Graph rendered to: {rendered_path}")
                    
                    if os.path.exists(rendered_path) and rendered_path.lower().endswith('.png'):
                        self.logger.info(f"Diagram successfully rendered to: {rendered_path}")
                        return relative_url_path
                    elif os.path.exists(output_filepath): # Check our expected path with .png
                        self.logger.info(f"Diagram successfully rendered, found at expected path: {output_filepath}")
                        return relative_url_path
                    else:
                        self.logger.error(f"Graphviz render did not produce expected PNG file. Checked: {rendered_path} and {output_filepath}. Render output from LLM may have been different or failed silently.")
                        # Attempt to list files in diagram_dir for debugging
                        try:
                            files_in_dir = os.listdir(diagram_dir)
                            self.logger.info(f"Files in {diagram_dir}: {files_in_dir}")
                            # Search for any PNG files that might have been created with a different name
                            png_files = [f for f in files_in_dir if f.endswith('.png') and f.startswith(os.path.basename(filepath_without_ext))]
                            if png_files:
                                self.logger.info(f"Found possible match: {png_files[0]}")
                                return f"diagrams/{png_files[0]}"
                        except Exception as e:
                            self.logger.error(f"Error listing directory: {e}")
                        
                        # Fallback: Try to render directly with the filename
                        try:
                            self.logger.info("Attempting direct render call as fallback")
                            graph_obj.render('diagram_output', view=False, cleanup=True)
                            
                            # Check if the fallback created a file
                            fallback_file = 'diagram_output.png'
                            if os.path.exists(fallback_file):
                                # Move the file to our target location
                                import shutil
                                shutil.move(fallback_file, output_filepath)
                                self.logger.info(f"Fallback render succeeded, moved to: {output_filepath}")
                                return relative_url_path
                        except Exception as e_fallback:
                            self.logger.error(f"Fallback render also failed: {e_fallback}")

                    # Try really hard to find any generated image before giving up
                    for ext in ['.png', '.jpg', '.jpeg', '.svg']:
                        potential_file = filepath_without_ext + ext
                        if os.path.exists(potential_file):
                            self.logger.info(f"Found image with different extension: {potential_file}")
                            # Adjust the relative URL path to match the actual extension
                            return f"diagrams/{os.path.basename(potential_file)}"
                else:
                    self.logger.error("Graphviz code did not define a discoverable Digraph object in local_namespace.")
                    # Look for any graph-related objects in namespace for debugging
                    graph_related = {name: type(val) for name, val in local_namespace.items()}
                    self.logger.error(f"Objects in namespace: {graph_related}")
                    return None
            except Exception as e_exec:
                self.logger.error(f"Error executing generated Graphviz code: {e_exec}", exc_info=True)
                return None

        try:
            image_file_path = await sync_to_async(_render_graphviz_sync, thread_sensitive=False)(graphviz_code, "diagram", user_query)
            return image_file_path 
        except Exception as e_render:
            self.logger.error(f"Error during sync_to_async call for Graphviz rendering: {e_render}", exc_info=True)
            return None
