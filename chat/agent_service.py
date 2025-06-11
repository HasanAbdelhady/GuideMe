import re
import logging
from .agent_tools import summarize_video, recommend_videos

logger = logging.getLogger(__name__)

def is_youtube_url(url: str) -> bool:
    """
    Checks if the given string is a valid YouTube video URL.
    """
    if not isinstance(url, str):
        return False
    # Regex to match YouTube video URLs (watch, youtu.be, shorts, etc.)
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    match = re.match(youtube_regex, url)
    return bool(match)

def run_youtube_agent(query: str):
    """
    Determines whether to summarize a YouTube video or recommend videos based on the query.
    This function acts as a router to the correct tool, bypassing the need for a LangChain agent,
    which was causing performance issues and rate-limiting errors.
    """
    try:
        logger.info(f"Processing YouTube request with query: {query}")
        
        if is_youtube_url(query):
            # If the query is a URL, summarize the video.
            logger.info("Query is a YouTube URL. Summarizing video...")
            result = summarize_video(query)
            logger.info(f"Summarization result: {result[:100]}...")
            return result
        else:
            # Otherwise, recommend videos based on the query topic.
            logger.info("Query is a search term. Recommending videos...")
            result = recommend_videos(query)
            # The result is expected to be a JSON string of video data
            logger.info(f"Recommendation result: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Error in YouTube agent router: {e}", exc_info=True)
        return "An error occurred while trying to process your request with the YouTube agent."
