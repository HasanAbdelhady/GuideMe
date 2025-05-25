from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from All_Tools_used import summarize_video, recommend_videos
load_dotenv("API.env")

# Initialize LLM (Using Groq's Llama3-70B model)
llm = ChatGroq(model="llama3-70b-8192", temperature=0)

# Define LangChain Tools
summarize_tool = Tool(
    name="Summarize Text",
    func=summarize_video,
    description=
        """Downloads a video from YouTube, extracts the audio, transcribes it using Whisper, 
        and generates a brief summary of the content. 
        Takes a YouTube link as input and returns a summary. 
        IMPORTANT: The output is already summarized. Do NOT summarize it again or pass it to any other summarization step."""
)

recommend_tool = Tool(
    name='Recommend Video',
    func=recommend_videos,
    description="""Use this tool when the user wants to find videos about a topic or subject.
    This tool will search YouTube and return a list of relevant video recommendations.
    The output will be formatted as a numbered list with titles and links.
    Use this for general queries about finding videos, not for summarizing specific videos."""
)

# Initialize Agent
agent = initialize_agent(
    tools=[recommend_tool, summarize_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs={
        "prefix": """You are an AI assistant specialized in handling YouTube video-related tasks. 
        You have two main capabilities:
        
        1. Video Summarization: When given a YouTube URL, use the Summarize Text tool to provide a summary of that specific video.
        
        2. Video Recommendations: When asked to find videos about a topic or subject, use the Recommend Video tool to provide relevant video suggestions.
        
        Guidelines:
        - For video recommendations: Use the Recommend Video tool when users ask about finding videos on a topic, searching for content, or want suggestions.
        - For video summaries: Use the Summarize Text tool only when given a specific YouTube URL to summarize.
        - Do not mix these tools - use each for its specific purpose.
        - When using the Summarize Text tool, return the exact output without additional processing.
        - When using the Recommend Video tool, return the formatted list of recommendations as provided by the tool."""
    }
)

# Test the agent
while True:
    test_topic = input("Enter what you want: ")
    if test_topic == "exit":
        break
    result = agent.invoke({"input": test_topic})
    print(result['output'])
