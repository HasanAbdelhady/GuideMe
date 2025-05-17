from .prompts import prompt_sys, prompt_fix_code, prompt_content
import yt_dlp
import textwrap
from groq import Groq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import time
import re
import traceback
from dotenv import load_dotenv


load_dotenv("API.env")


# Initialize LLM
llm = ChatGroq(model="llama3-70b-8192", temperature=0)

# Initialize embeddings for RAG
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Function to Download and Transcribe video and summarize text
def summarize_video(url, filename="audio"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '168',
        }],
        'outtmpl': filename,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    client = Groq()
    filename = f"{filename}.mp3" # Use the converted audio file
    with open(filename, "rb") as file:
        transcription = client.audio.transcriptions.create(
          file=(filename, file.read()),
          model="whisper-large-v3",
          response_format="verbose_json",
        )
    text = transcription.text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=50, separators=[" ", ",", "\n"]
    )
    texts = text_splitter.split_text(text)
    docs = [Document(page_content=t) for t in texts]
    chain = load_summarize_chain(llm, chain_type="stuff")
    summary = chain.run(docs)
    return textwrap.fill(summary, width=1000)

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Diagram Generation
def diagram_generation(text,k=4):
    vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    docs = vector_store.similarity_search(text, k=k)
    book_context = "\n\n".join([doc.page_content for doc in docs])
    prompt_content_diagram = prompt_content.format(book_context=book_context if book_context else "No book content available.")
    content = llm.invoke([SystemMessage(content=prompt_content_diagram)]) # , HumanMessage(content=text)
   
    # Get the Graphviz Python code from LLM
    response = llm.invoke([SystemMessage(content=prompt_sys), HumanMessage(content=content.content)])

    # Extract and clean the generated code
    response_text = response.content
    graphviz_code = response_text.split('```')[1].strip('python\n') if '```' in response_text else response_text.strip()

    # Handle the code execution safely with isolated namespace
    filename = f"diagram"
    filename = sanitize_filename(filename)

    # First attempt to execute the code
    try:
        exec(graphviz_code)
        return f"✅ Diagram generated successfully: {filename}.png"
    except Exception as e:
        error_message = f"{str(e)}\n\n{traceback.format_exc()}"
        print(f"❌ Initial attempt failed with error: {str(e)}")

        # Enter loop for error correction (up to 2 additional attempts)
        for i in range(2):
            # Prepare prompt to fix the code
            fix_prompt = prompt_fix_code.format(
                topic=text,
                description=content.content,
                erroneous_code=graphviz_code,
                error_message=error_message
            )

            # Get corrected code from LLM
            fix_response = llm.invoke([SystemMessage(content=fix_prompt)])
            fixed_code = fix_response.content

            # Clean the fixed code
            if '```' in fixed_code:
                fixed_code = fixed_code.split('```')[1].strip('python\n')
            else:
                fixed_code = fixed_code.strip()

            print(f"🛠️ Attempting to fix code for retry {i+1}/2")
            graphviz_code = fixed_code  # Update code for next attempt

            try:
                exec(graphviz_code)
                return f"✅ Diagram generated successfully: {filename}.png"
                
            except Exception as e:
                error_message = f"{str(e)}\n\n{traceback.format_exc()}"
                print(f"❌ Attempt {i+1}/2 failed with error: {str(e)}")
                if i == 1:
                    return f"❌ All attempts failed. Could not generate diagram."
                
