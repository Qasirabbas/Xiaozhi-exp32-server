from config.logger import setup_logging
from plugins_func.functions.story_detection import handle_story_request
import asyncio

TAG = __name__
logger = setup_logging()

async def handle_storytelling_intent(conn, text):
    """
    Handle story requests and pass them to the tell_story function.
    
    Args:
        conn: Connection object
        text: User input text
        
    Returns:
        bool: True if handled as a story request, False otherwise
    """
    # Try to handle as a story request
    story_result = handle_story_request(conn, text)
    
    if story_result:
        logger.bind(tag=TAG).info(f"Handled as story request: {text}")
        return True
    
    # Not a story request
    return False