import logging
import re

from .agent_tools import recommend_videos, summarize_video

logger = logging.getLogger(__name__)


def extract_youtube_url(text: str):
    """
    Extracts the first valid YouTube video URL from a string using regex.
    Returns the URL string if found, otherwise None.
    """
    if not isinstance(text, str):
        return None
    # This regex captures standard, shortened, and embed URLs.
    youtube_regex = (
        r"(https?://)?(www\.)?"
        r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
        r'(watch\?v=|embed/|v/|.+\?v=)?([^"&?\s]{11})'
    )
    match = re.search(youtube_regex, text)
    return match.group(0) if match else None


def run_youtube_agent(query: str, chat_history: list):
    """
    Determines whether to summarize a YouTube video or recommend videos based on the query.
    This function acts as a router to the correct tool, bypassing the need for a LangChain agent,
    which was causing performance issues and rate-limiting errors.
    """
    try:
        logger.info(f"Processing YouTube request with query: {query}")

        extracted_url = extract_youtube_url(query)

        if extracted_url:
            # If a URL is found anywhere in the query, summarize the video.
            logger.info(f"Extracted YouTube URL: {extracted_url}. Summarizing video...")
            result = summarize_video(extracted_url)
            logger.info(f"Summarization result: {result[:100]}...")
            return result
        else:
            # Otherwise, recommend videos based on the query topic.
            logger.info("No URL found. Recommending videos...")
            result = recommend_videos(query, chat_history)
            # The result is expected to be a JSON string of video data
            logger.info(f"Recommendation result: {result}")
            return result

    except Exception as e:
        logger.error(f"Error in YouTube agent router: {e}", exc_info=True)
        return "An error occurred while trying to process your request with the YouTube agent."
