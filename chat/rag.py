from langchain_huggingface.embeddings import HuggingFaceEndpointEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from pgvector.django import CosineDistance
import os
from pdfminer.high_level import extract_text
from dotenv import load_dotenv
from pathlib import Path
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)


class RAG_pipeline:
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2", model="llama3-8b-8192"):
        self.embedding_model_name = embedding_model_name
        self.model = model
        # Replace FAISS with None since we're using PostgreSQL
        self.vectorstore = None
        self.retriever = None
        self.qa_chain = None
        self.chunks = []

        # Keep embeddings for generating new embeddings
        # Use Hugging Face Inference API instead of local model to avoid heavy deps (torch/sentence-transformers)
        api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        if not api_token:
            raise ValueError(
                "HUGGINGFACEHUB_API_TOKEN is not set. Create a token at https://huggingface.co/settings/tokens and set it in your environment/.env."
            )

        # Accept either bare model name (e.g., "all-MiniLM-L6-v2") or full repo id
        model_id = (
            embedding_model_name
            if "/" in embedding_model_name
            else f"sentence-transformers/{embedding_model_name}"
        )

        # Use HuggingFaceEndpointEmbeddings which hits the Inference API
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model=model_id,
            task="feature-extraction",
            huggingfacehub_api_token=api_token,
        )

    def build_index(self, file_paths_and_types, chat_id=None, rag_files_map=None):
        """Build index using PostgreSQL instead of FAISS"""
        if not chat_id:
            raise ValueError(
                "chat_id is required for PostgreSQL vector storage")

        # Import here to avoid circular imports
        from .models import Chat, DocumentChunk, ChatVectorIndex

        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            print(f"Chat with id {chat_id} not found")
            return

        # Clear existing chunks for this chat
        DocumentChunk.objects.filter(chat=chat).delete()

        all_loaded_docs = []
        file_to_rag_file_map = {}

        # Process files (keep your existing file processing logic)
        for file_path, file_type in file_paths_and_types:
            docs_from_file = []
            if file_type == "pdf":
                try:
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        print(f"PDF file not found: {file_path}. Skipping.")
                        continue
                    text = extract_text(file_path)
                    if text and text.strip():
                        docs_from_file = [Document(page_content=text, metadata={
                                                   "source": os.path.basename(file_path), "file_path": file_path})]
                except Exception as e:
                    print(f"Failed to extract text from PDF {file_path}: {e}")
                    continue
            elif file_type == "txt":
                try:
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        print(f"Text file not found: {file_path}. Skipping.")
                        continue
                    loader = TextLoader(file_path, encoding="utf-8")
                    loaded_docs_segment = loader.load()
                    if loaded_docs_segment:
                        # Add file_path to metadata
                        for doc in loaded_docs_segment:
                            doc.metadata["file_path"] = file_path
                        docs_from_file = loaded_docs_segment
                except Exception as e:
                    print(f"Failed to load text file {file_path}: {e}")
                    continue

            # Map file path to rag_file if provided
            if rag_files_map and file_path in rag_files_map:
                file_to_rag_file_map[file_path] = rag_files_map[file_path]

            all_loaded_docs.extend(docs_from_file)

        if not all_loaded_docs:
            print("No documents were successfully loaded.")
            return

        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100)
        self.chunks = splitter.split_documents(all_loaded_docs)

        if not self.chunks:
            print("No chunks created from documents.")
            return

        # Generate embeddings for all chunks
        chunk_texts = [chunk.page_content for chunk in self.chunks]
        embeddings_list = self.embeddings.embed_documents(chunk_texts)

        # Store chunks with embeddings in PostgreSQL
        chunk_objects = []
        for i, (chunk, embedding) in enumerate(zip(self.chunks, embeddings_list)):
            # Find the corresponding RAG file using the file path
            rag_file = None
            file_path = chunk.metadata.get('file_path', '')
            if file_path and file_path in file_to_rag_file_map:
                rag_file = file_to_rag_file_map[file_path]
            else:
                # Fallback: try to find by filename
                source_file = chunk.metadata.get('source', '')
                if source_file:
                    try:
                        rag_file = ChatRAGFile.objects.filter(
                            chat=chat,
                            original_filename=source_file
                        ).first()
                    except:
                        pass

            if not rag_file:
                print(
                    f"Warning: Could not find RAG file for chunk {i}, file_path: {file_path}")
                continue  # Skip chunks without valid rag_file

            chunk_obj = DocumentChunk(
                chat=chat,
                rag_file=rag_file,
                content=chunk.page_content,
                chunk_index=i,
                embedding=embedding,
                metadata=chunk.metadata
            )
            chunk_objects.append(chunk_obj)

        # Bulk create all chunks
        DocumentChunk.objects.bulk_create(chunk_objects, batch_size=100)

        # Update or create vector index record
        ChatVectorIndex.objects.update_or_create(
            chat=chat,
            defaults={
                'total_chunks': len(chunk_objects),
                'embedding_model': self.embedding_model_name
            }
        )

        print(
            f"Successfully stored {len(chunk_objects)} chunks in PostgreSQL for chat {chat_id}")

    def retrieve_docs(self, query: str, chat_id=None):
        """Retrieve relevant documents from PostgreSQL using vector similarity"""
        if not chat_id:
            return []

        from .models import DocumentChunk

        # Generate embedding for the query
        query_embedding = self.embeddings.embed_query(query)

        # Perform vector similarity search using PostgreSQL
        chunks = DocumentChunk.objects.filter(
            chat_id=chat_id
        ).annotate(
            similarity=CosineDistance('embedding', query_embedding)
        ).order_by('similarity')[:4]  # Get top 4 most similar chunks

        # Convert back to LangChain Document format
        documents = []
        for chunk in chunks:
            doc = Document(
                page_content=chunk.content,
                metadata={
                    'source': chunk.metadata.get('source', 'unknown'),
                    'chunk_index': chunk.chunk_index,
                    'similarity_score': float(chunk.similarity),
                    **chunk.metadata
                }
            )
            documents.append(doc)

        return documents
