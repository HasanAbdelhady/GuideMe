import yt_dlp
import textwrap
from groq import Groq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain_groq import ChatGroq
import os
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from googleapiclient.discovery import build
import isodate
import traceback
from dotenv import load_dotenv
import imageio_ffmpeg
import json

load_dotenv(".env")

# Initialize LLM
llm = ChatGroq(model="llama3-8b-8192", temperature=0.3)

# Function to Download and Transcribe video and summarize text
def summarize_video(url, filename="audio"):
    try:
        # Validate URL format
        if not url.startswith(("https://www.youtube.com/", "https://youtu.be/")):
            return "Error: Please provide a valid YouTube URL"

        # Download video
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '168',
            }],
            'outtmpl': filename,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception as e:
            return f"Error downloading video: {str(e)}"

        # Transcribe audio
        try:
            client = Groq()
            filename = f"{filename}.mp3"
            with open(filename, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(filename, file.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                )
        except Exception as e:
            return f"Error transcribing audio: {str(e)}"
        finally:
            # Clean up the audio file
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass

        # Process and summarize text
        try:
            text = transcription.text
            if not text:
                return "Error: No text was extracted from the video"

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=50, separators=[" ", ",", "\\n"]
            )
            texts = text_splitter.split_text(text)
            docs = [Document(page_content=t) for t in texts]

            # Create a more direct prompt to avoid conversational filler
            prompt_template = """Summrize the following video transcript (don't say it's a video transcript)

"{text}"

SUMMARY:"""
            summary_prompt = PromptTemplate(template=prompt_template, input_variables=["text"])
            
            chain = load_summarize_chain(llm, chain_type="stuff", prompt=summary_prompt)
            summary = chain.run(docs)
            return textwrap.fill(summary, width=1000)
        except Exception as e:
            return f"Error processing text: {str(e)}"

    except Exception as e:
        return f"Unexpected error: {str(e)}"

youtube_api = os.getenv("YOUTUBE_API") 

# Importent variables
MAX_RESULTS = 10

def get_video_details(video_id):
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api, cache_discovery=False)
        
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=video_id
        ).execute()

        if not response['items']:
            return None

        video = response['items'][0]
        
        # Check if video is available
        if video['status'].get('privacyStatus') != 'public':
            return None
            
        # Check if video is not deleted
        if video['status'].get('uploadStatus') != 'processed':
            return None
        
        data = {
            'title': video['snippet']['title'],
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'thumbnail': f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
        } 
        # We are removing duration and other stats to keep it simple as requested.
        return data
    except Exception as e:
        print(f"Error getting video details: {str(e)}")
        return None

# Function to format video metadata
def formate_videos_metadata(videos):
    metadata = ""
    for idx, vid in enumerate(videos, start = 1):
        # Removed description from here
        metadata += f"{idx}. Title: {vid['title']}\n Link: {vid['url']}\n\n"
    
    return metadata

#Function to create a prompt for the LLM
def prompt(user_query, video_metadata_list):
    prompt_template = PromptTemplate(
        input_variables=["user_query", "video_metadata_list"],
        template= f"""
        You are an intelligent assistant helping users find the best YouTube videos.

        User message: "{user_query}"

        From the following videos, recommend the top 3 that are most relevant and useful, and most likely to be watched by the user.
        Provide your answer as a JSON object containing a key "recommendations" which is a list of video titles.
        
        Example:
        {{
            "recommendations": [
                "Deep Learning | What is Deep Learning? | Deep Learning Tutorial For Beginners | 2023 | Simplilearn",
                "But what is a neural network? | Deep learning chapter 1",
                "Deep Learning Crash Course for Beginners"
            ]
        }}

        Here is the list of videos to choose from:
        {video_metadata_list}
        """
)
   
    return prompt_template
                
def recommend_videos(user_query, chat_history):
    try:
        # Create a combined text of previous messages for context
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        # The agent should search based on the full context
        search_query = f"{history_text}\n\nUser Query: {user_query}"

        youtube = build("youtube", "v3", developerKey=youtube_api, cache_discovery=False)
        response = youtube.search().list(
            q=user_query, # We still use the user_query for the keyword search on youtube
            part="snippet",
            maxResults=MAX_RESULTS, # Reduced from * 2
            type="video", # Only search for videos
        ).execute()

        videos = []
        video_map = {}
        for item in response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                video_id = item["id"]["videoId"]
                video_data = get_video_details(video_id)
                if video_data:
                    videos.append(video_data)
                    video_map[video_data['title']] = video_data

        # Only proceed if we have enough valid videos
        if len(videos) >= 3:
            formatted_list = formate_videos_metadata(videos)
            
            prompt_text = f"""
                You are an intelligent assistant helping users find the best YouTube videos based on their conversation.

                This is the conversation history:
                {history_text}

                The user's latest message is: "{user_query}"

                From the following numbered list of videos, recommend the top 3 that are most relevant to the user's request in the context of the conversation.
                Provide your answer as a JSON object containing a key "recommendations" which is a list of the integer INDEXES of the videos.
                
                Example:
                {{
                    "recommendations": [1, 3, 5]
                }}

                Here is the list of videos to choose from:
                {formatted_list}
            """
            
            try:
                llm = ChatGroq(
                    model="llama3-8b-8192",
                    temperature=0.5,
                    max_retries=3 
                )

                response = llm.invoke(prompt_text)
                
                try:
                    # The response from invoke is an AIMessage object, we need its content
                    raw_response_content = response.content.strip()
                    
                    # Find the start and end of the JSON object to isolate it
                    json_start = raw_response_content.find('{')
                    json_end = raw_response_content.rfind('}')
                    
                    if json_start != -1 and json_end > json_start:
                        json_string = raw_response_content[json_start:json_end+1].strip()
                        
                        # Remove markdown backticks if they are wrapping the JSON
                        if json_string.startswith("```json"):
                            json_string = json_string[7:].strip()
                        if json_string.endswith("```"):
                            json_string = json_string[:-3].strip()
                        
                        response_data = json.loads(json_string)
                        recommended_indices = response_data.get("recommendations", [])
                        
                        # Create the final list of video objects from the indices
                        # Note: The prompt gives 1-based indices, so we subtract 1 for 0-based list access.
                        recommended_videos = []
                        for index in recommended_indices:
                            if isinstance(index, int) and 1 <= index <= len(videos):
                                recommended_videos.append(videos[index - 1])

                        # Return as a JSON string for the agent/service layer
                        return json.dumps(recommended_videos)
                    else:
                        # If we can't find a JSON object, raise an error
                        raise ValueError("Could not find a valid JSON object in the LLM response.")

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    return f"Error processing LLM response: {e}. Raw response: {response.content}"

            except Exception as e:
                return f"Error generating recommendations: {str(e)}"
        else:
            return "Not enough available videos found to make recommendations. Please try a different search query."
                
    except Exception as e:
        return f"Error searching for videos: {str(e)}"
