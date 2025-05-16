import re
from config.logger import setup_logging
from plugins_func.register import ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Patterns that indicate story requests
STORY_REQUEST_PATTERNS = [
    r'tell\s+(?:me\s+)?(?:a\s+)?story',
    r'read\s+(?:me\s+)?(?:a\s+)?story',
    r'(tell|narrate|read)\s+(?:me\s+)?(?:a\s+)?(novel|tale|fiction)',
    r'(?:can\s+you\s+)?(tell|narrate|read)(?:\s+to\s+me)?(?:\s+a\s+)?(story|novel|tale)',
    r'i\s+want\s+to\s+hear\s+(?:a\s+)?story',
    r'story\s+about',
    r'continue\s+(?:the\s+)?story',
    r'what\s+happens\s+next(?:\s+in\s+the\s+story)?',
    r'(?:can\s+you\s+)?finish\s+(?:the\s+)?story',
]

# Patterns for different story genres
GENRE_PATTERNS = {
    'fantasy': [r'fantasy', r'magic', r'wizard', r'dragon', r'elf', r'mythical', r'enchanted', r'fairy'],
    'sci-fi': [r'sci(?:\s+|\-)?fi', r'science\s+fiction', r'space', r'future', r'robot', r'alien', r'technology', r'futuristic'],
    'adventure': [r'adventure', r'quest', r'journey', r'expedition', r'exploration', r'discover'],
    'mystery': [r'mystery', r'detective', r'crime', r'solve', r'puzzle', r'suspense', r'thriller'],
    'horror': [r'horror', r'scary', r'ghost', r'spooky', r'creepy', r'terror', r'frightening'],
    'romance': [r'romance', r'love', r'relationship', r'couple', r'romantic'],
    'historical': [r'historical', r'history', r'ancient', r'medieval', r'past', r'era', r'century', r'period'],
    'comedy': [r'comedy', r'funny', r'humor', r'joke', r'amusing', r'hilarious'],
    'fairy tale': [r'fairy\s+tale', r'fairytale', r'princess', r'prince', r'kingdom', r'once\s+upon\s+a\s+time'],
    'fable': [r'fable', r'moral', r'lesson', r'animal', r'talking\s+animal'],
}

# Patterns for story themes
THEME_PATTERNS = {
    'friendship': [r'friend', r'friendship', r'companionship', r'buddy'],
    'family': [r'family', r'parent', r'child', r'sibling', r'mother', r'father', r'mom', r'dad', r'sister', r'brother'],
    'love': [r'love', r'relationship', r'romance', r'couple', r'boyfriend', r'girlfriend', r'husband', r'wife', r'wedding'],
    'courage': [r'courage', r'brave', r'hero', r'heroic', r'overcome', r'face\s+fear'],
    'adventure': [r'adventure', r'exploration', r'quest', r'journey', r'discover'],
    'mystery': [r'mystery', r'secret', r'enigma', r'puzzle', r'clue', r'detective'],
    'growth': [r'grow', r'growth', r'learn', r'change', r'mature', r'develop', r'overcome'],
    'redemption': [r'redemption', r'forgive', r'second\s+chance', r'make\s+amends', r'atone'],
    'conflict': [r'conflict', r'battle', r'war', r'fight', r'struggle', r'defeat', r'enemy'],
    'survival': [r'survival', r'survive', r'wilderness', r'lost', r'stranded', r'disaster'],
    'good vs evil': [r'good\s+vs\s+evil', r'hero\s+villain', r'light\s+dark', r'right\s+wrong'],
    'animal': [r'animal', r'pet', r'dog', r'cat', r'bear', r'lion', r'tiger', r'wolf', r'horse', r'dolphin', r'elephant'],
    'space': [r'space', r'planet', r'star', r'galaxy', r'universe', r'astronaut', r'alien'],
    'magic': [r'magic', r'wizard', r'witch', r'spell', r'wand', r'enchant', r'sorcery'],
    'nature': [r'nature', r'forest', r'mountain', r'river', r'sea', r'ocean', r'island', r'environment'],
}

# Patterns for audience types
AUDIENCE_PATTERNS = {
    'children': [r'child', r'children', r'kid', r'kids', r'young', r'little\s+one', r'bedtime', r'child(?:\'s|ren\'s)'],
    'teens': [r'teen', r'teenager', r'young\s+adult', r'ya', r'youth', r'adolescent'],
    'adults': [r'adult', r'grown[\s\-]up', r'mature'],
}

# Patterns for story length
LENGTH_PATTERNS = {
    'short': [r'short', r'brief', r'quick', r'little', r'small'],
    'medium': [r'medium', r'moderate', r'average', r'normal'],
    'long': [r'long', r'detailed', r'elaborate', r'extended', r'complete'],
}

# Patterns for story continuation
CONTINUATION_PATTERNS = [
    r'continue\s+(?:the\s+)?story',
    r'what\s+happens\s+next',
    r'tell\s+(?:me\s+)?more',
    r'(?:and\s+)?then\s+what\s+happened',
    r'go\s+on',
    r'next\s+part',
    r'finish\s+(?:the\s+)?story',
    r'part\s+two',
    r'second\s+part',
]

def detect_story_request(text):
    """
    Detect if the text is requesting a story
    
    Args:
        text: The text to analyze
        
    Returns:
        bool: True if the text is requesting a story, False otherwise
    """
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Check if the text matches any story request pattern
    for pattern in STORY_REQUEST_PATTERNS:
        if re.search(pattern, text):
            logger.bind(tag=TAG).info(f"Detected story request: {text}")
            return True
            
    return False

def detect_story_continuation(text):
    """
    Detect if the text is requesting to continue a story
    
    Args:
        text: The text to analyze
        
    Returns:
        bool: True if the text is requesting to continue a story
    """
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Check if the text matches any continuation pattern
    for pattern in CONTINUATION_PATTERNS:
        if re.search(pattern, text):
            logger.bind(tag=TAG).info(f"Detected story continuation request: {text}")
            return True
            
    return False

def extract_story_params(text):
    """
    Extract story parameters from the text
    
    Args:
        text: The text to analyze
        
    Returns:
        dict: Dictionary of story parameters
    """
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Default parameters
    params = {
        'genre': 'fantasy',
        'theme': 'adventure',
        'audience': 'adults',
        'length': 'medium',
        'continue_story': False
    }
    
    # Check for continuation request
    params['continue_story'] = detect_story_continuation(text)
    
    # Extract genre
    for genre, patterns in GENRE_PATTERNS.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', text):
                params['genre'] = genre
                logger.bind(tag=TAG).info(f"Detected genre: {genre}")
                break
    
    # Extract theme
    for theme, patterns in THEME_PATTERNS.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', text):
                params['theme'] = theme
                logger.bind(tag=TAG).info(f"Detected theme: {theme}")
                break
    
    # Extract audience
    for audience, patterns in AUDIENCE_PATTERNS.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', text):
                params['audience'] = audience
                logger.bind(tag=TAG).info(f"Detected audience: {audience}")
                break
    
    # Extract length
    for length, patterns in LENGTH_PATTERNS.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', text):
                params['length'] = length
                logger.bind(tag=TAG).info(f"Detected length: {length}")
                break
    
    # Handle special cases where theme might be explicitly mentioned
    theme_match = re.search(r'(?:story|tale)\s+about\s+(?:a\s+)?([a-z\s]+)', text)
    if theme_match:
        # Extract the potential theme
        potential_theme = theme_match.group(1).strip()
        if len(potential_theme) > 0 and len(potential_theme) < 50:
            logger.bind(tag=TAG).info(f"Extracted explicit theme: {potential_theme}")
            params['theme'] = potential_theme
    
    return params

def handle_story_request(conn, text):
    """
    Handle a story request
    
    Args:
        conn: Connection object
        text: The text of the request
        
    Returns:
        ActionResponse: The story response or None if not a story request
    """
    # Check if this is a story request
    if not detect_story_request(text) and not detect_story_continuation(text):
        return None
    
    # Extract story parameters
    params = extract_story_params(text)
    logger.bind(tag=TAG).info(f"Story parameters: {params}")
    
    # Check if we have a tell_story function handler
    if not hasattr(conn, 'func_handler'):
        logger.bind(tag=TAG).error("Connection does not have func_handler attribute")
        return None
    
    # Check if the tell_story function is registered
    func = conn.func_handler.get_function('tell_story')
    if not func:
        logger.bind(tag=TAG).error("tell_story function not registered")
        return None
    
    # Call the tell_story function
    try:
        function_call_data = {
            "name": "tell_story",
            "id": "story_request",
            "arguments": json.dumps(params)
        }
        return conn.func_handler.handle_llm_function_call(conn, function_call_data)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Error calling tell_story function: {str(e)}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Error generating story: {str(e)}",
            response="I'm sorry, I had trouble creating a story. Would you like me to try again?"
        )